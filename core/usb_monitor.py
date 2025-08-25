# core/usb_monitor.py
import re
import threading
import time

import wmi
import pythoncom

VID_PID_RE = re.compile(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", re.IGNORECASE)


def parse_ids(pnp_id: str):
    """
    Extract VID, PID, Vendor, Product, Serial if available.
    Returns dict with any fields found.
    """
    ids = {"vid": None, "pid": None, "vendor": None, "product": None, "serial": None}

    if not pnp_id:
        return ids

    # Standard VID/PID pattern
    vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", pnp_id)
    pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", pnp_id)

    if vid_match:
        ids["vid"] = vid_match.group(1).upper()
    if pid_match:
        ids["pid"] = pid_match.group(1).upper()

    # Fallback: text-based identifiers
    ven_match = re.search(r"VEN_([A-Z0-9]+)", pnp_id, re.IGNORECASE)
    prod_match = re.search(r"PROD_([A-Z0-9_]+)", pnp_id, re.IGNORECASE)

    if ven_match:
        ids["vendor"] = ven_match.group(1).upper()
    if prod_match:
        ids["product"] = prod_match.group(1).upper()

    # Serial is usually the last chunk after "\"
    parts = pnp_id.split("\\")
    if len(parts) >= 3:
        ids["serial"] = parts[-1]

    return ids



# core/usb_monitor.py (add this helper)
def parse_serial(pnp_id: str | None):
    # Example PNPDeviceID: "USB\\VID_0781&PID_5567\\2004A1B2C3D4..."
    if not pnp_id:
        return None
    parts = pnp_id.split("\\")
    return parts[-1] if len(parts) >= 3 else None

def parse_vid_pid(pnp_id: str):
    # print(f"DEBUG raw PNPDeviceID: {pnp_id}")
    if not pnp_id:
        return None, None
    m = VID_PID_RE.search(pnp_id)
    if not m:
        return None, None
    return m.group(1).upper(), m.group(2).upper()

def monitor_usb_storage(on_event):
    """
    Calls on_event(dict) for insert/remove of USB Disk Drives.
    dict keys: action ('insert'|'remove'), model, pnp_id, vid, pid, timestamp
    """
    def _run():
        pythoncom.CoInitialize()
        c = wmi.WMI()
        insert_watcher = c.watch_for(
            notification_type="Creation",
            wmi_class="Win32_DiskDrive",
            InterfaceType="USB"
        )
        remove_watcher = c.watch_for(
            notification_type="Deletion",
            wmi_class="Win32_DiskDrive",
            InterfaceType="USB"
        )
        while True:
            # Wait for either insert or remove; alternate checks to keep it simple
            try:
                inserted = insert_watcher(timeout_ms=500)
                
                if inserted:
                    vid, pid = parse_vid_pid(inserted.PNPDeviceID)
                    ids = parse_ids(inserted.PNPDeviceID)
                    on_event({
                        "action": "insert",
                        "model": inserted.Model,
                        "pnp_id": inserted.PNPDeviceID,
                        "vid": vid,
                        "pid": pid,
                        "vendor": ids["vendor"],
                        "product": ids["product"],
                        "serial": ids["serial"],
                        "timestamp": time.time(),
                    })
            except wmi.x_wmi_timed_out:
                pass
            try:
                removed = remove_watcher(timeout_ms=10)
                if removed:
                    vid, pid = parse_vid_pid(removed.PNPDeviceID)
                    ids = parse_ids(removed.PNPDeviceID)
                    on_event({
                        "action": "remove",
                        "model": removed.Model,
                        "pnp_id": removed.PNPDeviceID,
                        "vid": vid,
                        "pid": pid,
                        "vendor": ids["vendor"],
                        "product": ids["product"],
                        "serial": ids["serial"],
                        "timestamp": time.time(),
                    })
            except wmi.x_wmi_timed_out:
                pass
        # pythoncom.CoUninitialize()  # unreachable in this simple loop

    t = threading.Thread(target=_run, daemon=True)
    t.start()
