# Speedometer for Windows 11

Speedometer is a lightweight, TrafficMonitor-inspired live network and system
monitor for Windows 11. It measures real-time upload and download throughput
from Windows network adapter counters—not synthetic web speed tests—alongside
CPU and memory utilization.

## Direct Download

Download and run directly on Windows 11 (no Python or extra dependencies required):

| Package | Description | Download |
| --- | --- | --- |
| **Portable App** | Single standalone executable (`Speedometer.exe`) — run directly from any folder | [Download Speedometer.exe](https://github.com/drkanurag/SPEEDOMETER/raw/main/dist/Speedometer.exe) |
| **Windows Installer** | Installs to `%LOCALAPPDATA%\Speedometer` with Start Menu & Desktop shortcuts | [Download Speedometer-Setup.exe](https://github.com/drkanurag/SPEEDOMETER/raw/main/dist/Speedometer-Setup.exe) |

> **Quick Start:** Double-click `Speedometer.exe` to launch the taskbar-sized
> live monitor (`Taskbar Strip`). Right-click the monitor or system tray icon at
> any time for **Window Skin**, **Align to Taskbar**, **Connection Details**,
> **Historical Traffic Statistics**, and **Options**.

## Key Features

- **Main Floating Window (4 Skins):** Switch between **Taskbar Strip**
  (sized to fit inside the Windows 11 taskbar), **Compact Pill**, **Modern Card**,
  and **Detailed Dashboard** with Windows 11 rounded corners, live
  download/upload sparkline graph, CPU/RAM bars, session totals, and edge
  snapping.
- **Embedded Taskbar Window:** Toggle a compact **Taskbar Window** (Two-Row or
  Single-Row Horizontal) positioned cleanly inside the Windows 11 taskbar next
  to the notification tray or widgets, with automatic Light/Dark theme matching.
- **TrafficMonitor-Style Context Menu:** Right-click either overlay or the
  system tray icon to switch network adapters, toggle windows, lock window
  position, enable **Mouse Penetrate (click-through)**, or enable
  **Auto-Hide on Fullscreen**.
- **Connection Details:** Inspect IPv4/IPv6 addresses, MAC address, link speed,
  MTU, packet counts, and error/drop counters for any interface.
- **Historical Traffic Statistics:** Persists daily download and upload usage in
  `%APPDATA%\Speedometer\history.json` with Today / 7-Day / Month / All-Time
  summaries, a 14-day visual bar chart, and CSV export.
- **Tabbed Options Dialog:** Configure adapter mode (`All active adapters`,
  `Auto (Primary active)`, or individual adapters), speed units (`Auto bits/s`,
  `Auto Bytes/s`, `Fixed KB/s`, `Fixed MB/s`, `Fixed Mbps`), themes (`Midnight`,
  `Windows 11 Dark`, `Windows 11 Light`, `Graphite`, `Nord`), custom colors,
  fonts, opacity, and custom metric prefixes.
- **Live System Tray Tooltip:** Hover over the tray icon at any time to see
  live download/upload speeds and CPU/RAM usage.

## Use the Portable EXE

Run `dist\Speedometer.exe` directly—no installation is required. Its settings
and daily traffic history are stored locally in `%APPDATA%\Speedometer\`.
To install into `%LOCALAPPDATA%\Speedometer` with Start Menu and Desktop
shortcuts, run `dist\Speedometer-Setup.exe`.

## Build from Source

On Windows, run `build.ps1`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build.ps1
```

Or run directly with Python:

```powershell
pip install -r requirements.txt
python speedometer.py
```

## Architecture & Signing

- See [ARCHITECTURE.md](ARCHITECTURE.md) for module boundaries and reliability
  rules.
- See [SIGNING.md](SIGNING.md) for Authenticode signing instructions for Windows
  Smart App Control.
