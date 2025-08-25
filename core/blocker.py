# core/blocker.py
import subprocess
import ctypes

def is_admin() -> bool:
    """Return True if the current process has Administrator rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _ps_quote(s: str) -> str:
    """
    Quote for PowerShell: wrap in double-quotes and escape any ` or " inside.
    """
    return '"' + s.replace('`', '``').replace('"', '`"') + '"'

def _run_powershell(cmd: str, timeout: int = 8):
    """
    Run a short PowerShell command with safe defaults.
    Returns (returncode, stdout, stderr).
    """
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=timeout
    )
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()

def disable_device(instance_id: str):
    """
    Disable the PnP device with the exact InstanceId.
    Requires Admin. Returns (success: bool, message: str).
    """
    if not is_admin():
        return False, "Admin rights required to disable devices."
    quoted = _ps_quote(instance_id)
    # Try to disable; return 'OK' on success or the exception message if it fails.
    cmd = (
        f"try {{ Disable-PnpDevice -InstanceId {quoted} -Confirm:$false -ErrorAction Stop; 'OK' }}"
        f" catch {{ $_.Exception.Message }}"
    )
    code, out, err = _run_powershell(cmd)
    if code == 0 and "OK" in out:
        return True, "Device disabled."
    # Some systems print warnings to stdout; prefer stderr if present.
    return False, (err or out or "Disable-PnpDevice failed.")

def enable_device(instance_id: str):
    """
    Enable the PnP device with the exact InstanceId.
    Requires Admin. Returns (success: bool, message: str).
    """
    if not is_admin():
        return False, "Admin rights required to enable devices."
    quoted = _ps_quote(instance_id)
    cmd = (
        f"try {{ Enable-PnpDevice -InstanceId {quoted} -Confirm:$false -ErrorAction Stop; 'OK' }}"
        f" catch {{ $_.Exception.Message }}"
    )
    code, out, err = _run_powershell(cmd)
    if code == 0 and "OK" in out:
        return True, "Device enabled."
    return False, (err or out or "Enable-PnpDevice failed.")
