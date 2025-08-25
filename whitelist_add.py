# tools/whitelist_add.py
import sys
from core.db import DB

USAGE = """
Usage:
  python tools/whitelist_add.py <label> <vid> <pid> [serial]
  python tools/whitelist_add.py --serial-only <label> <serial>

Examples:
  python tools/whitelist_add.py "Office SanDisk" 0781 5567 2004A1B2C3D4
  python tools/whitelist_add.py --serial-only "ADATA Personal" "27C0717200120064&0"
"""

args = sys.argv[1:]
if not args:
    print(USAGE); sys.exit(1)

db = DB()

if args[0] == "--serial-only":
    if len(args) != 3:
        print(USAGE); sys.exit(1)
    label, serial = args[1], args[2]
    db.whitelist_add_serial(label, serial)
    print(f"Whitelisted by serial: {label} S/N:{serial}")
else:
    if len(args) < 3:
        print(USAGE); sys.exit(1)
    label, vid, pid = args[0], args[1], args[2]
    serial = args[3] if len(args) >= 4 else None
    db.whitelist_add(label, vid, pid, serial)
    print(f"Whitelisted: {label} VID:{(vid or '').upper()} PID:{(pid or '').upper()} S/N:{serial or '—'}")
