Project Implementation Description

The USB Access Control System will be developed as a standalone desktop application that runs on Windows computers. The goal is to detect and control the use of USB devices, preventing unauthorized access and logging all activity for security review.

Programming Language:
The system will be built in Python, chosen because it is reliable, lightweight, and allows rapid development.

USB Detection:
We will use Windows Management Instrumentation (WMI) through Python libraries (wmi, pywin32) to detect when a USB device is plugged in or removed. This lets the software capture details such as the device name, ID, and time of connection.

Database & Storage:
All data (USB logs and approved devices) will be stored locally in a SQLite database. SQLite is a lightweight and secure database that does not need any server setup, making the system easy to deploy and maintain.

Access Control (Whitelist):
The system will maintain a whitelist of authorized USB devices. If a device is not on the whitelist, it will be flagged, and the user will receive an immediate alert.

Alerts & Notifications:
Unauthorized USB devices will trigger real-time notifications on the computer screen. This ensures that IT staff or users are instantly aware of suspicious activity.

Graphical User Interface (GUI):
A simple interface will be created using Tkinter (Python’s built-in GUI library).

One tab will show a list of all past USB connections (logs).

Another tab will allow administrators to add or remove devices from the whitelist.

There will also be simple options to configure whether devices should be blocked, allowed, or just monitored.

Final Output:
The project will be packaged into a Windows executable (.exe) using PyInstaller, so it can run directly on client machines without needing to install Python manually.



Languages & Technologies

Python 3.10+ → the main programming language (lightweight, reliable, and fast for development).

SQLite → local database to store USB activity logs and the whitelist of approved devices.

Tkinter → Python’s built-in GUI (Graphical User Interface) library, used to create the admin panel.

Libraries / Plugins (Python Modules)

wmi → to interact with Windows Management Instrumentation (WMI) and detect USB devices in real time.

pywin32 → gives access to Windows system functions, required for USB event handling.

win10toast → to display Windows-style notifications when unauthorized devices are connected.

sqlite3 (built-in with Python) → to interact with the SQLite database for logging and whitelist checks.

PyInstaller → to package the entire system into a Windows .exe file so it can run without needing Python installed.

Development Tools

Visual Studio Code (VS Code) → code editor used to write and test the system.

Windows 10/11 PC → target platform where the system will run.



Starting in CLI

# Create & activate a virtual environment
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python .\main.py

# Upgrade pip and install deps
python -m pip install --upgrade pip
pip install wmi pywin32 win10toast pyinstaller




Incase you lock the device out completely
🔍 Step 1: Check if Windows still sees the device

Open Device Manager (devmgmt.msc).

Expand Disk drives.

Look for your pendrive (ADATA).

If it’s there with a little down arrow icon → it’s disabled.

If it’s missing completely → Windows is not enumerating it (either still blocked, or physically not reconnecting).