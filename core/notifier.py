# core/notifier.py
from plyer import notification

def notify(title: str, message: str, duration: int = 5):
    """
    Show a desktop notification using plyer.
    duration ignored on Windows (handled by OS).
    """
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=duration
        )
    except Exception as e:
        print(f"[Notifier Error] {e}")
