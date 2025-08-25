# core/db.py
import os
import time
import sqlite3
import threading
import bcrypt  # make sure to install: pip install bcrypt

DEFAULT_DB_PATH = os.path.join("data", "usb_guard.db")

def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    x = str(x).strip()
    return x.upper() if x else None


class DB:
    def __init__(self, path: str = DEFAULT_DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.lock = threading.Lock()
        self._migrate()

    def _migrate(self):
        with self.lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS whitelist (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  label   TEXT,
                  vid     TEXT,
                  pid     TEXT,
                  serial  TEXT,
                  created_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_whitelist_serial ON whitelist(serial);

                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts       INTEGER,
                  action   TEXT,
                  model    TEXT,
                  pnp_id   TEXT,
                  vid      TEXT,
                  pid      TEXT,
                  serial   TEXT,
                  decision TEXT,
                  note     TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

                CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash BLOB NOT NULL
                );
                """
            )

    # ---------- User / Password ops ----------
    def add_user(self, username: str, password: str) -> bool:
        """Add a new user. Returns False if user exists."""
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        try:
            with self.lock, self.conn:
                self.conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, pw_hash),
                )
            return True
        except sqlite3.IntegrityError:
            return False  # username already exists

    def verify_user(self, username: str, password: str) -> bool:
        """Verify credentials."""
        cur = self.conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            return False
        stored_hash = row[0]
        return bcrypt.checkpw(password.encode(), stored_hash)

    def change_password(self, username: str, new_password: str) -> bool:
        """Change user password. Returns False if user not found."""
        pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        with self.lock, self.conn:
            cur = self.conn.execute(
                "UPDATE users SET password_hash=? WHERE username=?",
                (pw_hash, username),
            )
        return cur.rowcount > 0

    # ---------- Whitelist ops ----------
    def whitelist_add(self, label: str, vid: str | None, pid: str | None, serial: str | None):
        vid = _norm(vid)
        pid = _norm(pid)
        serial = _norm(serial)
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO whitelist(label, vid, pid, serial, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (label, vid, pid, serial, int(time.time())),
            )

    def whitelist_add_serial(self, label: str, serial: str):
        self.whitelist_add(label=label, vid=None, pid=None, serial=serial)

    def whitelist_remove(self, vid: str | None, pid: str | None, serial: str | None):
        vid = _norm(vid)
        pid = _norm(pid)
        serial = _norm(serial)
        with self.lock, self.conn:
            if vid and pid:
                self.conn.execute(
                    """
                    DELETE FROM whitelist
                    WHERE vid=? AND pid=? AND (serial = ? OR (serial IS NULL AND ? IS NULL))
                    """,
                    (vid, pid, serial, serial),
                )
            elif serial:
                self.conn.execute("DELETE FROM whitelist WHERE serial = ?", (serial,))

    def whitelist_contains(self, vid: str | None, pid: str | None, serial: str | None) -> bool:
        vid = _norm(vid)
        pid = _norm(pid)
        serial = _norm(serial)
        with self.lock, self.conn:
            if not vid or not pid:
                if not serial:
                    return False
                cur = self.conn.execute("SELECT 1 FROM whitelist WHERE serial = ? LIMIT 1", (serial,))
                return cur.fetchone() is not None
            cur = self.conn.execute(
                """
                SELECT 1
                FROM whitelist
                WHERE vid=? AND pid=? AND (serial = ? OR (serial IS NULL AND ? IS NULL))
                LIMIT 1
                """,
                (vid, pid, serial, serial),
            )
            return cur.fetchone() is not None

    # ---------- Event logging ----------
    def log_event(
        self,
        ts: float,
        action: str,
        model: str | None,
        pnp_id: str | None,
        vid: str | None,
        pid: str | None,
        serial: str | None,
        decision: str,
        note: str | None = None,
    ):
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO events(ts, action, model, pnp_id, vid, pid, serial, decision, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(ts), action, model, pnp_id, _norm(vid), _norm(pid), _norm(serial), decision, note),
            )

    def list_whitelist(self):
        cur = self.conn.cursor()
        cur.execute("SELECT serial FROM whitelist")
        rows = cur.fetchall()
        return [{"serial": row[0]} for row in rows]

    def remove_whitelist(self, serial):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM whitelist WHERE serial=?", (serial,))
        self.conn.commit()

    def list_recent_blocked(self, since_minutes: int = 60, limit: int = 100):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ts, model, pnp_id, vid, pid, serial, note
            FROM events
            WHERE action='insert' AND decision='blocked' AND ts >= strftime('%s','now') - ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (since_minutes * 60, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "ts": r[0],
                "model": r[1],
                "pnp_id": r[2],
                "vid": r[3],
                "pid": r[4],
                "serial": r[5],
                "note": r[6],
            }
            for r in rows
        ]
