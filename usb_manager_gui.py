# usb_manager_gui.py
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv

from core.db import DB
from core.usb_monitor import monitor_usb_storage
from core.guardian import process_event
from core.blocker import is_admin, enable_device

db = DB()

# background monitoring uses the same enforcement logic
def watcher():
    monitor_usb_storage(lambda evt: process_event(evt, db))


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
            self.tree_blocked.column(c,
                                     width=140 if c == "when" else 240 if c in ("model", "note") else 320,
                                     anchor="w")
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

        # schedule periodic refresh
        self.after(2000, self._periodic_refresh)

        # initial load
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

        # Add to whitelist by serial
        db.whitelist_add_serial(model or "Unknown", serial)

        # Try to enable immediately (requires admin)
        if is_admin() and pnp_id:
            ok, msg = enable_device(pnp_id)
            if ok:
                messagebox.showinfo("Whitelisted", f"Whitelisted & enabled:\n{model}\nS/N: {serial}")
            else:
                messagebox.showwarning("Whitelisted", f"Whitelisted, but enable failed:\n{msg}\nYou may replug the device.")
        else:
            messagebox.showinfo("Whitelisted", f"Whitelisted:\n{model}\nS/N: {serial}\n(Replug if not visible.)")

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
        self.decision_filter = ttk.Combobox(filter_frame,
                                            values=["All", "allowed", "blocked", "observe"],
                                            state="readonly", width=12)
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
            "note": "Note"
        }

        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=150 if c in ("when", "decision", "action") else 220, anchor="w")

        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        # schedule periodic refresh
        self.after(3000, self._periodic_refresh)

        # initial load
        self.refresh()

    def refresh(self):
        # Clear
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Decision filter
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
        cur.execute("SELECT ts, action, decision, model, serial, vid, pid, pnp_id, note FROM events ORDER BY ts DESC")
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


class USBManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Manager — Whitelist & Logs")
        self.root.geometry("1100x700")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self.whitelist_tab = WhitelistTab(notebook)
        self.logs_tab = LogsTab(notebook)

        notebook.add(self.whitelist_tab, text="Whitelist")
        notebook.add(self.logs_tab, text="Logs")

        # Menu (optional): quick refresh
        menubar = tk.Menu(root)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh All", command=self.refresh_all)
        menubar.add_cascade(label="View", menu=view_menu)
        root.config(menu=menubar)

    def refresh_all(self):
        self.whitelist_tab.refresh()
        self.logs_tab.refresh()


if __name__ == "__main__":
    # start monitor thread (daemon so app can exit normally)
    threading.Thread(target=watcher, daemon=True).start()

    root = tk.Tk()
    app = USBManagerApp(root)
    root.mainloop()
