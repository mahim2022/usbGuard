# logs_gui.py
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from core.db import DB

db = DB()

class LogsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Events Log Viewer")

        # --- Filters ---
        filter_frame = ttk.Frame(root)
        filter_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(filter_frame, text="Decision:").pack(side="left", padx=5)
        self.decision_filter = ttk.Combobox(filter_frame, values=["All", "allowed", "blocked", "observe"], state="readonly")
        self.decision_filter.current(0)
        self.decision_filter.pack(side="left")

        ttk.Button(filter_frame, text="Apply Filter", command=self.refresh).pack(side="left", padx=10)
        ttk.Button(filter_frame, text="Export CSV", command=self.export_csv).pack(side="left", padx=10)

        # --- Events Table ---
        cols = ("when", "action", "decision", "model", "serial", "vid", "pid", "pnp_id", "note")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", height=20)

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
            self.tree.column(c, width=150 if c in ("when","decision","action") else 220, anchor="w")

        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

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
        query += " ORDER BY ts DESC LIMIT 500"

        cur = db.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        for r in rows:
            ts = datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S")
            self.tree.insert("", "end", values=(ts, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))

    def export_csv(self):
        import csv
        from tkinter import filedialog, messagebox

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


if __name__ == "__main__":
    root = tk.Tk()
    app = LogsGUI(root)
    root.mainloop()
