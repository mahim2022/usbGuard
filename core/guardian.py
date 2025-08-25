# core/guardian.py
from core.db import DB
from core.notifier import notify
from core.blocker import is_admin, disable_device, enable_device

def process_event(evt: dict, db: DB):
    """
    Decide + enforce + log + notify.
    Returns a dict with decision and note.
    """
    action = evt["action"]
    model = evt.get("model")
    pnp_id = evt.get("pnp_id")
    vid = evt.get("vid")
    pid = evt.get("pid")
    serial = evt.get("serial")

    if action == "insert":
        whitelisted = db.whitelist_contains(vid, pid, serial)
        decision = "allowed" if whitelisted else "blocked"

        if decision == "blocked":
            if is_admin():
                ok, msg = disable_device(pnp_id)
                note = f"not on whitelist; {'disabled' if ok else 'disable failed: ' + msg}"
            else:
                note = "not on whitelist; NOT disabled (needs admin)"
        else:
            # Best-effort enable
            if is_admin():
                ok, msg = enable_device(pnp_id)
                note = f"on whitelist; {'enabled' if ok else 'enable attempt: ' + msg}"
            else:
                note = "on whitelist"
    else:
        decision = "observe"
        note = "device removed"

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

    # Console + toast
    key = f"VID:{vid} PID:{pid}" if (vid and pid) else "SERIAL-ONLY"
    serial_str = serial or "—"
    print(f"[{action.upper()}] {model or 'Unknown Model'} | {key} S/N:{serial_str} -> {decision.upper()} ({note})")

    if action == "insert":
        notify(f"USB {decision.upper()}", f"{model or 'Unknown'}\n{key} S/N:{serial_str}\n{note}", duration=7)
    elif action == "remove":
        notify("USB Removed", f"{model or 'Unknown'}\nS/N:{serial_str}", duration=4)

    return {"decision": decision, "note": note}
