# usb_manager_gui.py
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime
import csv

from core.db import DB
from core.usb_monitor import monitor_usb_storage
from core.guardian import process_event
from core.blocker import is_admin, enable_device

db = DB()

# ---------------------------
# Background watcher
# ---------------------------
def watcher():
    monitor_usb_storage(lambda evt: process_event(evt, db))


# ---------------------------
# Auth dialogs (DB-backed)
# ---------------------------
def _users_count() -> int:
    cur = db.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    (n,) = cur.fetchone()
    return int(n or 0)


class SetupDialog(simpledialog.Dialog):
    """Shown on first run when there are no users. Creates the first admin user."""

    def body(self, master):
        self.title("Initial Setup — Create Admin User")

        ttk.Label(master, text="Username:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        ttk.Label(master, text="Password:").grid(row=1, column=0, padx=6, pady=6, sticky="e")
        ttk.Label(master, text="Confirm Password:").grid(row=2, column=0, padx=6, pady=6, sticky="e")

        self.username_var = tk.StringVar(value="admin")
        self.pw1_var = tk.StringVar()
        self.pw2_var = tk.StringVar()

        self.e_user = ttk.Entry(master, textvariable=self.username_var)
        self.e_pw1 = ttk.Entry(master, textvariable=self.pw1_var, show="*")
        self.e_pw2 = ttk.Entry(master, textvariable=self.pw2_var, show="*")

        self.e_user.grid(row=0, column=1, padx=6, pady=6)
        self.e_pw1.grid(row=1, column=1, padx=6, pady=6)
        self.e_pw2.grid(row=2, column=1, padx=6, pady=6)

        return self.e_user

    def validate(self):
        u = self.username_var.get().strip()
        p1 = self.pw1_var.get()
        p2 = self.pw2_var.get()
        if not u:
            messagebox.showerror("Setup", "Username is required.")
            return False
        if not p1:
            messagebox.showerror("Setup", "Password is required.")
            return False
        if p1 != p2:
            messagebox.showerror("Setup", "Passwords do not match.")
            return False
        return True

    def apply(self):
        u = self.username_var.get().strip()
        p1 = self.pw1_var.get()
        ok = db.add_user(u, p1)
        if not ok:
            messagebox.showerror("Setup", f'User "{u}" already exists. Choose a different username.')
            self.result = None
        else:
            self.result = u


class LoginDialog(simpledialog.Dialog):
    """Prompts for username/password and verifies against DB."""

    def body(self, master):
        self.title("Login")

        ttk.Label(master, text="Username:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        ttk.Label(master, text="Password:").grid(row=1, column=0, padx=6, pady=6, sticky="e")

        self.username_var = tk.StringVar(value="admin")
        self.password_var = tk.StringVar()

        self.e_user = ttk.Entry(master, textvariable=self.username_var)
        self.e_pw = ttk.Entry(master, textvariable=self.password_var, show="*")

        self.e_user.grid(row=0, column=1, padx=6, pady=6)
        self.e_pw.grid(row=1, column=1, padx=6, pady=6)

        return self.e_user

    def apply(self):
        u = self.username_var.get().strip()
        p = self.password_var.get()
        if not db.verify_user(u, p):
            messagebox.showerror("Access Denied", "Incorrect username or password.")
            self.result = None
        else:
            self.result = u  # return the logged-in username


class ChangePasswordDialog(simpledialog.Dialog):
    """Change password for the currently logged-in user."""

    def __init__(self, parent, username: str):
        self.username = username
        super().__init__(parent)

    def body(self, master):
        self.title(f"Change Password — {self.username}")

        ttk.Label(master, text="Current Password:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        ttk.Label(master, text="New Password:").grid(row=1, column=0, padx=6, pady=6, sticky="e")
        ttk.Label(master, text="Confirm New Password:").grid(row=2, column=0, padx=6, pady=6, sticky="e")

        self.cur_var = tk.StringVar()
        self.n1_var = tk.StringVar()
        self.n2_var = tk.StringVar()

        self.e_cur = ttk.Entry(master, textvariable=self.cur_var, show="*")
        self.e_n1 = ttk.Entry(master, textvariable=self.n1_var, show="*")
        self.e_n2 = ttk.Entry(master, textvariable=self.n2_var, show="*")

        self.e_cur.grid(row=0, column=1, padx=6, pady=6)
        self.e_n1.grid(row=1, column=1, padx=6, pady=6)
        self.e_n2.grid(row=2, column=1, padx=6, pady=6)

        return self.e_cur

    def validate(self):
        cur = self.cur_var.get()
        n1 = self.n1_var.get()
        n2 = self.n2_var.get()

        if not db.verify_user(self.username, cur):
            messagebox.showerror("Change Password", "Current password is incorrect.")
            return False
        if not n1:
            messagebox.showerror("Change Password", "New password is required.")
            return False
        if n1 != n2:
            messagebox.showerror("Change Password", "New passwords do not match.")
            return False
        return True

    def apply(self):
        ok = db.change_password(self.username, self.n1_var.get())
        if not ok:
            messagebox.showerror("Change Password", "Failed to change password.")
            self.result = None
        else:
            messagebox.showinfo("Change Password", "Password updated successfully.")
            self.result = True


# ---------------------------
# Tabs
# ---------------------------
class WhitelistTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # --- Recently Blocked ---
        frame1 = ttk.LabelFrame(self, text="Recently Blocked (last 60 minutes)")
        frame1.pack(fill="both", expand=True, padx=10, pady=5)

        cols_blocked = ("when", "model", "serial", "pnp_id", "note")
        self.tree_blocked = ttk.Treeview(frame1, columns=cols_blocked, show="headings", height=10)
        for c, hdr in zip(cols_blocked, ("When", "Model", "Serial", "InstanceId", "Note")):
            self.tree_blocked.heading(c, text=hdr)
            self.tree_blocked.column(
                c,
                width=140 if c == "when" else 240 if c in ("model", "note") else 320,
                anchor="w",
            )
        self.tree_blocked.pack(fill="both", expand=True)

        btns1 = ttk.Frame(frame1)
        btns1.pack(fill="x", pady=4)
        ttk.Button(btns1, text="Whitelist & Enable", command=self.whitelist_and_enable).pack(side="left", padx=4)
        ttk.Button(btns1, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        # --- Whitelist ---
        frame2 = ttk.LabelFrame(self, text="Whitelisted Serials")
        frame2.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree_wl = ttk.Treeview(frame2, columns=("serial",), show="headings", height=8)
        self.tree_wl.heading("serial", text="Serial")
        self.tree_wl.column("serial", width=320)
        self.tree_wl.pack(fill="both", expand=True)

        btns2 = ttk.Frame(frame2)
        btns2.pack(fill="x", pady=4)
        ttk.Button(btns2, text="Remove from Whitelist", command=self.remove_from_whitelist).pack(side="left", padx=4)
        ttk.Button(btns2, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        # periodic refresh
        self.after(2000, self._periodic_refresh)
        self.refresh()

    def refresh(self):
        # blocked list
        for i in self.tree_blocked.get_children():
            self.tree_blocked.delete(i)
        for r in db.list_recent_blocked(since_minutes=60, limit=200):
            when = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            self.tree_blocked.insert("", "end", values=(when, r["model"], r["serial"], r["pnp_id"], r["note"]))

        # whitelist list
        for i in self.tree_wl.get_children():
            self.tree_wl.delete(i)
        for row in db.list_whitelist():
            self.tree_wl.insert("", "end", values=(row["serial"],))

    def whitelist_and_enable(self):
        sel = self.tree_blocked.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a blocked item first.")
            return
        when, model, serial, pnp_id, note = self.tree_blocked.item(sel, "values")

        if not serial:
            messagebox.showerror("Missing serial", "Blocked record has no serial; cannot whitelist.")
            return

        db.whitelist_add_serial(model or "Unknown", serial)

        if is_admin() and pnp_id:
            ok, msg = enable_device(pnp_id)
            if ok:
                messagebox.showinfo("Whitelisted", f"Whitelisted & enabled:\n{model}\nS/N: {serial}")
            else:
                messagebox.showwarning(
                    "Whitelisted",
                    f"Whitelisted, but enable failed:\n{msg}\nYou may replug the device.",
                )
        else:
            messagebox.showinfo(
                "Whitelisted",
                f"Whitelisted:\n{model}\nS/N: {serial}\n(Replug if not visible.)",
            )
        self.refresh()

    def remove_from_whitelist(self):
        sel = self.tree_wl.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a whitelist entry first.")
            return
        serial = self.tree_wl.item(sel, "values")[0]
        db.remove_whitelist(serial)
        messagebox.showinfo("Removed", f"Removed S/N: {serial} from whitelist.")
        self.refresh()

    def _periodic_refresh(self):
        try:
            self.refresh()
        finally:
            self.after(2000, self._periodic_refresh)


class LogsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # --- Filters ---
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(filter_frame, text="Decision:").pack(side="left", padx=5)
        self.decision_filter = ttk.Combobox(
            filter_frame,
            values=["All", "allowed", "blocked", "observe"],
            state="readonly",
            width=12,
        )
        self.decision_filter.current(0)
        self.decision_filter.pack(side="left")

        ttk.Button(filter_frame, text="Apply Filter", command=self.refresh).pack(side="left", padx=10)
        ttk.Button(filter_frame, text="Export CSV", command=self.export_csv).pack(side="left", padx=10)

        # --- Events Table ---
        cols = ("when", "action", "decision", "model", "serial", "vid", "pid", "pnp_id", "note")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)

        headers = {
            "when": "Timestamp",
            "action": "Action",
            "decision": "Decision",
            "model": "Model",
            "serial": "Serial",
            "vid": "VID",
            "pid": "PID",
            "pnp_id": "InstanceId",
            "note": "Note",
        }

        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=150 if c in ("when", "decision", "action") else 220, anchor="w")

        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        # periodic refresh
        self.after(3000, self._periodic_refresh)
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        dec_filter = self.decision_filter.get()
        query = "SELECT ts, action, decision, model, serial, vid, pid, pnp_id, note FROM events"
        params = []
        if dec_filter != "All":
            query += " WHERE decision = ?"
            params.append(dec_filter)
        query += " ORDER BY ts DESC LIMIT 1000"

        cur = db.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        for r in rows:
            ts = datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S")
            self.tree.insert("", "end", values=(ts, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))

    def export_csv(self):
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file:
            return

        cur = db.conn.cursor()
        cur.execute(
            "SELECT ts, action, decision, model, serial, vid, pid, pnp_id, note FROM events ORDER BY ts DESC"
        )
        rows = cur.fetchall()

        with open(file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Action", "Decision", "Model", "Serial", "VID", "PID", "InstanceId", "Note"])
            for r in rows:
                ts = datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([ts, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])

        messagebox.showinfo("Exported", f"Logs exported to {file}")

    def _periodic_refresh(self):
        try:
            self.refresh()
        finally:
            self.after(3000, self._periodic_refresh)


# ---------------------------
# Main App
# ---------------------------
class USBManagerApp:
    def __init__(self, root, username: str):
        self.root = root
        self.username = username

        self.root.title(f"USB Manager — Whitelist & Logs (Logged in as: {self.username})")
        self.root.geometry("1100x700")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self.whitelist_tab = WhitelistTab(notebook)
        self.logs_tab = LogsTab(notebook)

        notebook.add(self.whitelist_tab, text="Whitelist")
        notebook.add(self.logs_tab, text="Logs")

        # Menu
        menubar = tk.Menu(root)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh All", command=self.refresh_all)
        menubar.add_cascade(label="View", menu=view_menu)

        account_menu = tk.Menu(menubar, tearoff=0)
        account_menu.add_command(label="Change Password", command=self.change_password)
        menubar.add_cascade(label="Account", menu=account_menu)

        root.config(menu=menubar)

    def refresh_all(self):
        self.whitelist_tab.refresh()
        self.logs_tab.refresh()

    def change_password(self):
        dlg = ChangePasswordDialog(self.root, self.username)
        # result handled inside dialog; nothing else required here


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # hide main window during auth

    # First-run setup if no users exist
    try:
        if _users_count() == 0:
            created = None
            while created is None:
                setup = SetupDialog(root)
                created = setup.result
                if created is None:
                    if messagebox.askyesno("Exit", "Setup incomplete. Exit the application?"):
                        root.destroy()
                        raise SystemExit
    except Exception as e:
        messagebox.showerror("Error", f"Database initialization failed:\n{e}")
        root.destroy()
        raise SystemExit

    # Login
    login_user = None
    while login_user is None:
        dlg = LoginDialog(root)
        login_user = dlg.result
        if login_user is None:
            if messagebox.askyesno("Exit", "Login cancelled or failed. Exit the application?"):
                root.destroy()
                raise SystemExit

    # Auth OK -> show app
    root.deiconify()

    # start monitor thread (daemon so app can exit normally)
    threading.Thread(target=watcher, daemon=True).start()

    app = USBManagerApp(root, username=login_user)
    root.mainloop()
