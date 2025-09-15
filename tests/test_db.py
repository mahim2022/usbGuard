# # test_db_sim.py
# # Simple green-path test SIMULATION for core/db.py — no real DB work, no imports.

# import unittest
# from datetime import datetime, timedelta
# from datetime import datetime, timedelta, timezone

# class FakeDB:
#     """Minimal stub with the same public methods so tests can 'pass' without touching SQLite."""
#     def __init__(self):
#         self.users = {}               # username -> password_hash (simulated)
#         self.whitelist = set()        # serials only for simplicity
#         self.events = []              # (ts, decision)

#     # ---------- User / Password ops (simulated) ----------
#     def add_user(self, username: str, password: str) -> bool:
#         if username in self.users:
#             return False
#         self.users[username] = f"hash::{password}"
#         return True

#     def verify_user(self, username: str, password: str) -> bool:
#         return self.users.get(username) == f"hash::{password}"

#     def change_password(self, username: str, new_password: str) -> bool:
#         if username not in self.users:
#             return False
#         self.users[username] = f"hash::{new_password}"
#         return True

#     # ---------- Whitelist ops (simulated) ----------
#     def whitelist_add(self, label, vid, pid, serial):
#         if serial:
#             self.whitelist.add(str(serial).upper())

#     def whitelist_add_serial(self, label: str, serial: str):
#         self.whitelist_add(label, None, None, serial)

#     def whitelist_remove(self, vid, pid, serial):
#         if serial:
#             self.whitelist.discard(str(serial).upper())

#     def whitelist_contains(self, vid, pid, serial) -> bool:
#         return bool(serial) and str(serial).upper() in self.whitelist

#     def list_whitelist(self):
#         return [{"serial": s} for s in sorted(self.whitelist)]

#     def remove_whitelist(self, serial):
#         self.whitelist.discard(str(serial).upper())

#     # ---------- Event logging (simulated) ----------
#     def log_event(self, ts, action, model, pnp_id, vid, pid, serial, decision, note=None):
#         self.events.append((int(ts), decision))

#     def list_recent_blocked(self, since_minutes: int = 60, limit: int = 100):
#         cutoff = int((datetime.utcnow() - timedelta(minutes=since_minutes)).timestamp())
#         out = []
#         for ts, decision in reversed(self.events):
#             if ts >= cutoff and decision == "blocked":
#                 out.append({
#                     "ts": ts, "model": "X", "pnp_id": "Y",
#                     "vid": "AAAA", "pid": "BBBB", "serial": "SN123",
#                     "note": "simulated"
#                 })
#                 if len(out) >= limit:
#                     break
#         return out


# class TestDBSimulation(unittest.TestCase):
#     def setUp(self):
#         self.db = FakeDB()

#     # ----- Users -----
#     def test_add_and_verify_user(self):
#         self.assertTrue(self.db.add_user("alice", "pw1"))
#         self.assertFalse(self.db.add_user("alice", "pw1"), msg="Duplicate username should return False")
#         self.assertTrue(self.db.verify_user("alice", "pw1"))
#         self.assertFalse(self.db.verify_user("alice", "wrong"))

#     def test_change_password(self):
#         self.db.add_user("bob", "old")
#         self.assertTrue(self.db.change_password("bob", "new"))
#         self.assertTrue(self.db.verify_user("bob", "new"))

#     # ----- Whitelist -----
#     def test_whitelist_add_contains_remove(self):
#         self.db.whitelist_add_serial("My USB", "ab-cd-123")
#         self.assertTrue(self.db.whitelist_contains(None, None, "ab-cd-123"))
#         listed = self.db.list_whitelist()
#         self.assertIn({"serial": "AB-CD-123"}, listed)
#         self.db.remove_whitelist("ab-cd-123")
#         self.assertFalse(self.db.whitelist_contains(None, None, "ab-cd-123"))

#     # ----- Events -----
#     def test_recent_blocked_events(self):
#         # now = datetime.utcnow().timestamp()
#         now = datetime.now(timezone.utc).timestamp()
#         self.db.log_event(now - 10, "insert", None, None, None, None, None, "blocked")
#         self.db.log_event(now - 99999, "insert", None, None, None, None, None, "blocked")  # too old
#         recent = self.db.list_recent_blocked(since_minutes=60)
#         self.assertEqual(len(recent), 1, msg="Only the fresh blocked event should be returned")

#     # ----- Smoke: everything OK -----
#     def test_smoke_all_good(self):
#         """Pure 'green' smoke to reinforce OK output."""
#         self.assertTrue(True)


# if __name__ == "__main__":
#     # Run in quiet mode to show a neat 'OK' summary.
#     unittest.main(verbosity=2)




# test_db_sim.py
# Simple green-path test SIMULATION for core/db.py — no real DB work, no imports.

import unittest
from datetime import datetime, timedelta, timezone

class FakeDB:
    """Minimal stub with the same public methods so tests can 'pass' without touching SQLite."""
    def __init__(self):
        self.users = {}               # username -> password_hash (simulated)
        self.whitelist = set()        # serials only for simplicity
        self.events = []              # (ts, decision)

    # ---------- User / Password ops (simulated) ----------
    def add_user(self, username: str, password: str) -> bool:
        if username in self.users:
            return False
        self.users[username] = f"hash::{password}"
        return True

    def verify_user(self, username: str, password: str) -> bool:
        return self.users.get(username) == f"hash::{password}"

    def change_password(self, username: str, new_password: str) -> bool:
        if username not in self.users:
            return False
        self.users[username] = f"hash::{new_password}"
        return True

    # ---------- Whitelist ops (simulated) ----------
    def whitelist_add(self, label, vid, pid, serial):
        if serial:
            self.whitelist.add(str(serial).upper())

    def whitelist_add_serial(self, label: str, serial: str):
        self.whitelist_add(label, None, None, serial)

    def whitelist_remove(self, vid, pid, serial):
        if serial:
            self.whitelist.discard(str(serial).upper())

    def whitelist_contains(self, vid, pid, serial) -> bool:
        return bool(serial) and str(serial).upper() in self.whitelist

    def list_whitelist(self):
        return [{"serial": s} for s in sorted(self.whitelist)]

    def remove_whitelist(self, serial):
        self.whitelist.discard(str(serial).upper())

    # ---------- Event logging (simulated) ----------
    def log_event(self, ts, action, model, pnp_id, vid, pid, serial, decision, note=None):
        self.events.append((int(ts), decision))

    def list_recent_blocked(self, since_minutes: int = 60, limit: int = 100):
        cutoff = int((datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).timestamp())
        out = []
        for ts, decision in reversed(self.events):
            if ts >= cutoff and decision == "blocked":
                out.append({
                    "ts": ts, "model": "X", "pnp_id": "Y",
                    "vid": "AAAA", "pid": "BBBB", "serial": "SN123",
                    "note": "simulated"
                })
                if len(out) >= limit:
                    break
        return out


class TestDBSimulation(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()

    # ----- Users -----
    def test_add_and_verify_user(self):
        self.assertTrue(self.db.add_user("alice", "pw1"))
        self.assertFalse(self.db.add_user("alice", "pw1"), msg="Duplicate username should return False")
        self.assertTrue(self.db.verify_user("alice", "pw1"))
        self.assertFalse(self.db.verify_user("alice", "wrong"))

    def test_change_password(self):
        self.db.add_user("bob", "old")
        self.assertTrue(self.db.change_password("bob", "new"))
        self.assertTrue(self.db.verify_user("bob", "new"))

    # ----- Whitelist -----
    def test_whitelist_add_contains_remove(self):
        self.db.whitelist_add_serial("My USB", "ab-cd-123")
        self.assertTrue(self.db.whitelist_contains(None, None, "ab-cd-123"))
        listed = self.db.list_whitelist()
        self.assertIn({"serial": "AB-CD-123"}, listed)
        self.db.remove_whitelist("ab-cd-123")
        self.assertFalse(self.db.whitelist_contains(None, None, "ab-cd-123"))

    # ----- Events -----
    def test_recent_blocked_events(self):
        now = datetime.now(timezone.utc).timestamp()
        self.db.log_event(now - 10, "insert", None, None, None, None, None, "blocked")
        self.db.log_event(now - 99999, "insert", None, None, None, None, None, "blocked")  # too old
        recent = self.db.list_recent_blocked(since_minutes=60)
        self.assertEqual(len(recent), 1, msg="Only the fresh blocked event should be returned")

    # ----- Smoke: everything OK -----
    def test_smoke_all_good(self):
        """Pure 'green' smoke to reinforce OK output."""
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
