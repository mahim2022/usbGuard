import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime

from core.db import DB
from core.usb_monitor import monitor_usb_storage
from core.guardian import process_event
from core.blocker import is_admin, enable_device

db = DB()

# background monitoring uses the same enforcement logic
def watcher():
    monitor_usb_storage(lambda evt: process_event(evt, db))

class WhitelistGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Whitelist Manager (Quarantine Mode)")

        # --- Recently Blocked ---
        frame1 = ttk.LabelFrame(root, text="Recently Blocked (last 60 minutes)")
        frame1.pack(fill="both", expand=True, padx=10, pady=5)

        cols_blocked = ("when", "model", "serial", "pnp_id", "note")
        self.tree_blocked = ttk.Treeview(frame1, columns=cols_blocked, show="headings", height=10)
        for c, hdr in zip(cols_blocked, ("When", "Model", "Serial", "InstanceId", "Note")):
            self.tree_blocked.heading(c, text=hdr)
            self.tree_blocked.column(c, width=140 if c=="when" else 240 if c in ("model","note") else 320, anchor="w")
        self.tree_blocked.pack(fill="both", expand=True)

        btns1 = ttk.Frame(frame1)
        btns1.pack(fill="x", pady=4)
        ttk.Button(btns1, text="Whitelist & Enable", command=self.whitelist_and_enable).pack(side="left", padx=4)
        ttk.Button(btns1, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        # --- Whitelist ---
        frame2 = ttk.LabelFrame(root, text="Whitelisted Serials")
        frame2.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree_wl = ttk.Treeview(frame2, columns=("serial",), show="headings", height=8)
        self.tree_wl.heading("serial", text="Serial")
        self.tree_wl.column("serial", width=320)
        self.tree_wl.pack(fill="both", expand=True)

        btns2 = ttk.Frame(frame2)
        btns2.pack(fill="x", pady=4)
        ttk.Button(btns2, text="Remove from Whitelist", command=self.remove_from_whitelist).pack(side="left", padx=4)
        ttk.Button(btns2, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        self.refresh()
        # periodic auto-refresh
        self.root.after(2000, self.refresh)

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

if __name__ == "__main__":
    # run monitor (with enforcement) in the background
    threading.Thread(target=watcher, daemon=True).start()
    root = tk.Tk()
    app = WhitelistGUI(root)
    root.mainloop()
