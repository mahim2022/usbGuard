# main.py
from core.usb_monitor import monitor_usb_storage
from core.db import DB
from core.notifier import notify
from core.blocker import is_admin, disable_device, enable_device
from core.guardian import process_event

db = DB()

def handle_event(evt: dict):
    action = evt["action"]
    model = evt.get("model")
    pnp_id = evt.get("pnp_id")
    vid = evt.get("vid")
    pid = evt.get("pid")
    serial = evt.get("serial")
    process_event(evt, db)

    # Decide first
    if action == "insert":
        whitelisted = db.whitelist_contains(vid, pid, serial)
        decision = "allowed" if whitelisted else "blocked"

        # Enforce (soft-block / enable) before logging so note reflects result
        if decision == "blocked":
            ok, msg = disable_device(pnp_id)
            note = f"not on whitelist; {'disabled' if ok else 'disable failed: ' + msg}"
        else:
            ok, msg = enable_device(pnp_id)
            # Enabling is best-effort; it may already be enabled
            note = f"on whitelist; {'enabled' if ok else 'enable attempt: ' + msg}"
    else:
        decision = "observe"
        note = "device removed"

    # Log to DB
    db.log_event(
        ts=evt["timestamp"],
        action=action,
        model=model,
        pnp_id=pnp_id,
        vid=vid,
        pid=pid,
        serial=serial,
        decision=decision,
        note=note,
    )

    # Console feedback
    key = f"VID:{vid} PID:{pid}" if (vid and pid) else "SERIAL-ONLY"
    serial_str = serial or "—"
    print(f"[{action.upper()}] {model or 'Unknown Model'} | {key} S/N:{serial_str} -> {decision.upper()} ({note})")

    # Notifications
    if action == "insert":
        title = f"USB {decision.upper()}"
        msg = f"{model or 'Unknown'}\n{key} S/N:{serial_str}\n{note}"
        notify(title, msg, duration=7)
    elif action == "remove":
        title = "USB Removed"
        msg = f"{model or 'Unknown'}\nS/N:{serial_str}"
        notify(title, msg, duration=4)

if __name__ == "__main__":
    if not is_admin():
        print("⚠️  WARNING: Not running as Administrator. Soft-blocking will NOT work.")
        print("    Right-click PowerShell/Terminal → ‘Run as administrator’, then start the app again.\n")

    print("USB detector + logger running. Plug/unplug a USB storage device to test.")
    monitor_usb_storage(handle_event)
    import time
    while True:
        time.sleep(1)
