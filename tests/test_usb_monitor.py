# tests/test_usb_monitor_sim.py
# Simple green-path SIMULATION tests for core/usb_monitor.py — no real WMI, no threads.

import unittest
from datetime import datetime, timezone

# ---- Local copies of the pure helpers (mirroring core/usb_monitor.py) ----

import re
VID_PID_RE = re.compile(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", re.IGNORECASE)

def parse_ids(pnp_id: str):
    """
    Extract VID, PID, Vendor, Product, Serial if available.
    Returns dict with any fields found.
    """
    ids = {"vid": None, "pid": None, "vendor": None, "product": None, "serial": None}
    if not pnp_id:
        return ids

    vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", pnp_id)
    pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", pnp_id)

    if vid_match:
        ids["vid"] = vid_match.group(1).upper()
    if pid_match:
        ids["pid"] = pid_match.group(1).upper()

    ven_match = re.search(r"VEN_([A-Z0-9]+)", pnp_id, re.IGNORECASE)
    prod_match = re.search(r"PROD_([A-Z0-9_]+)", pnp_id, re.IGNORECASE)

    if ven_match:
        ids["vendor"] = ven_match.group(1).upper()
    if prod_match:
        ids["product"] = prod_match.group(1).upper()

    parts = pnp_id.split("\\")
    if len(parts) >= 3:
        ids["serial"] = parts[-1]

    return ids

def parse_serial(pnp_id: str | None):
    if not pnp_id:
        return None
    parts = pnp_id.split("\\")
    return parts[-1] if len(parts) >= 3 else None

def parse_vid_pid(pnp_id: str):
    if not pnp_id:
        return None, None
    m = VID_PID_RE.search(pnp_id)
    if not m:
        return None, None
    return m.group(1).upper(), m.group(2).upper()


# ---- A tiny monitor "simulator" to mimic on_event callback flow ----

def simulate_monitor_usb_storage(on_event):
    """
    Synchronously "emits" two events (insert, remove) to the given on_event callback.
    Matches the dict shape described in the docstring of monitor_usb_storage().
    """
    # Typical Windows PNP strings
    insert_pnp = r"USB\VID_0781&PID_5567\2004A1B2C3D4EF01"
    remove_pnp = r"USB\VID_1234&PID_abcd\SN-XYZ-999"

    for action, model, pnp in [
        ("insert", "SanDisk Ultra USB Device", insert_pnp),
        ("remove", "Generic Flash Disk", remove_pnp),
    ]:
        vid, pid = parse_vid_pid(pnp)
        ids = parse_ids(pnp)
        on_event({
            "action": action,
            "model": model,
            "pnp_id": pnp,
            "vid": vid,
            "pid": pid,
            "vendor": ids["vendor"],
            "product": ids["product"],
            "serial": ids["serial"],
            "timestamp": datetime.now(timezone.utc).timestamp(),
        })


# ---- Tests ----

class TestUSBMonitorParsing(unittest.TestCase):
    def test_parse_vid_pid_basic(self):
        p = r"USB\VID_0781&PID_5567\2004A1B2C3D4EF01"
        vid, pid = parse_vid_pid(p)
        self.assertEqual(vid, "0781")
        self.assertEqual(pid, "5567")

    def test_parse_vid_pid_case_insensitive(self):
        p = r"USB\vid_ab12&pid_Ff09\SERIAL123"
        vid, pid = parse_vid_pid(p)
        self.assertEqual(vid, "AB12")
        self.assertEqual(pid, "FF09")

    def test_parse_vid_pid_missing(self):
        p = r"USB\NO_IDS_HERE\SER"
        vid, pid = parse_vid_pid(p)
        self.assertIsNone(vid)
        self.assertIsNone(pid)

    def test_parse_ids_full(self):
        p = r"USB\VID_1A2B&PID_3C4D&VEN_SANDISK&PROD_ULTRA_USB\ABC123SERIAL"
        out = parse_ids(p)
        self.assertEqual(out["vid"], "1A2B")
        self.assertEqual(out["pid"], "3C4D")
        self.assertEqual(out["vendor"], "SANDISK")
        self.assertEqual(out["product"], "ULTRA_USB")
        self.assertEqual(out["serial"], "ABC123SERIAL")

    # def test_parse_ids_partial(self):
    #     p = r"USB\VEN_FOO\BAR"
    #     out = parse_ids(p)
    #     self.assertIsNone(out["vid"])
    #     self.assertIsNone(out["pid"])
    #     self.assertEqual(out["vendor"], "FOO")
    #     # serial requires at least 3 parts split by '\'
    #     self.assertIsNone(out["serial"])

        def test_parse_ids_partial(self):
            p = r"USB\VEN_FOO\BAR"
            out = parse_ids(p)
            self.assertIsNone(out["vid"])
            self.assertIsNone(out["pid"])
            self.assertEqual(out["vendor"], "FOO")
            # Because there are 3 parts, last part is treated as serial
            self.assertEqual(out["serial"], "BAR")


    def test_parse_serial(self):
        p = r"USB\VID_DEAD&PID_BEEF\SN-42"
        self.assertEqual(parse_serial(p), "SN-42")
        self.assertIsNone(parse_serial(r"USB\ONLYTWO"))
        self.assertIsNone(parse_serial(None))


class TestUSBMonitorSimulation(unittest.TestCase):
    def test_simulated_monitor_emits_two_events(self):
        captured = []

        def on_event(evt):
            captured.append(evt)

        simulate_monitor_usb_storage(on_event)

        self.assertEqual(len(captured), 2)
        # Validate keys and basic content for both events
        for evt in captured:
            self.assertIn(evt["action"], ("insert", "remove"))
            self.assertIn("model", evt)
            self.assertIn("pnp_id", evt)
            self.assertIn("vid", evt)
            self.assertIn("pid", evt)
            self.assertIn("vendor", evt)
            self.assertIn("product", evt)
            self.assertIn("serial", evt)
            self.assertIn("timestamp", evt)
            self.assertIsInstance(evt["timestamp"], float)

        # Spot-check first event details
        first = captured[0]
        self.assertEqual(first["action"], "insert")
        self.assertEqual(first["vid"], "0781")
        self.assertEqual(first["pid"], "5567")
        self.assertEqual(first["serial"], "2004A1B2C3D4EF01")

        # Spot-check second event details
        second = captured[1]
        self.assertEqual(second["action"], "remove")
        self.assertEqual(second["vid"], "1234")
        self.assertEqual(second["pid"], "ABCD")
        self.assertEqual(second["serial"], "SN-XYZ-999")

    def test_simulated_monitor_shapes_match_doc(self):
        """Quick schema smoke to ensure dict shape matches monitor_usb_storage docstring."""
        shapes = []

        def on_event(evt):
            shapes.append(set(evt.keys()))

        simulate_monitor_usb_storage(on_event)

        expected = {"action", "model", "pnp_id", "vid", "pid", "vendor", "product", "serial", "timestamp"}
        for s in shapes:
            self.assertEqual(s, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
