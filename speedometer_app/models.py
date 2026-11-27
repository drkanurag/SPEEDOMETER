"""Core configuration, theme presets, DTOs, and formatting helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "Speedometer"
APP_VERSION = "2.0.0"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

FONTS = ("Segoe UI", "Bahnschrift", "Consolas", "Cascadia Mono", "Arial", "Calibri")

SKINS = ("Taskbar Strip", "Compact Pill", "Modern Card", "Detailed Dashboard")

UNIT_MODES = (
    "Auto (bits/s)",
    "Auto (Bytes/s)",
    "Fixed KB/s",
    "Fixed MB/s",
    "Fixed Mbps",
)

THEMES: dict[str, dict[str, str]] = {
    "Midnight": {
        "background": "#12161F",
        "surface": "#1B2230",
        "border": "#2A3447",
        "foreground": "#F3F6FC",
        "muted": "#8F9BB3",
        "download": "#3FE0A8",
        "upload": "#69B1FF",
        "cpu": "#F5B971",
        "ram": "#C084FC",
    },
    "Windows 11 Dark": {
        "background": "#1E1E1E",
        "surface": "#282828",
        "border": "#3A3A3A",
        "foreground": "#FFFFFF",
        "muted": "#A6A6A6",
        "download": "#6CCB5F",
        "upload": "#60CDFF",
        "cpu": "#FCE100",
        "ram": "#C58AF9",
    },
    "Windows 11 Light": {
        "background": "#F7F9FC",
        "surface": "#FFFFFF",
        "border": "#D8E0EB",
        "foreground": "#182233",
        "muted": "#5C6B80",
        "download": "#087F5B",
        "upload": "#1D63DC",
        "cpu": "#C76B00",
        "ram": "#7E3AF2",
    },
    "Graphite": {
        "background": "#23252A",
        "surface": "#2D3037",
        "border": "#3E424C",
        "foreground": "#F8FAFC",
        "muted": "#9CA3AF",
        "download": "#6EE7B7",
        "upload": "#93C5FD",
        "cpu": "#FBBF24",
        "ram": "#F472B6",
    },
    "Nord": {
        "background": "#2E3440",
        "surface": "#3B4252",
        "border": "#4C566A",
        "foreground": "#ECEFF4",
        "muted": "#D8DEE9",
        "download": "#88C0D0",
        "upload": "#A3BE8C",
        "cpu": "#EBCB8B",
        "ram": "#B48EAD",
    },
}


@dataclass
class Settings:
    schema_version: int = 2
    # Network & sampling
    adapter: str = "All active adapters"
    show_virtual_adapters: bool = False
    interval: float = 1.0
    unit_mode: str = "Auto (bits/s)"
    precision: int = 1

    # Visibility & windows
    show_main_window: bool = True
    show_taskbar_window: bool = False
    skin: str = "Taskbar Strip"
    compact: bool = False

    # Main floating window appearance
    font: str = "Segoe UI"
    font_size: int = 10
    background: str = "#12161F"
    surface: str = "#1B2230"
    border: str = "#2A3447"
    foreground: str = "#F3F6FC"
    muted: str = "#8F9BB3"
    download: str = "#3FE0A8"
    upload: str = "#69B1FF"
    cpu: str = "#F5B971"
    ram: str = "#C084FC"
    opacity: float = 0.96

    # Main window items
    show_download: bool = True
    show_upload: bool = True
    show_totals: bool = True
    show_system_stats: bool = True
    show_sparkline: bool = True
    show_adapter_name: bool = True

    # Main window behavior
    always_on_top: bool = True
    lock_position: bool = False
    mouse_penetrate: bool = False
    auto_hide_fullscreen: bool = True
    dock_to_taskbar: bool = True
    dock_side: str = "Right"
    window_x: int | None = None
    window_y: int | None = None

    # Taskbar window settings (TrafficMonitor-style)
    taskbar_side: str = "Right"  # Right (next to tray) | Left (next to widgets)
    taskbar_offset_x: int = 8
    taskbar_layout: str = "Two-Row"  # Two-Row | Horizontal
    taskbar_auto_theme: bool = True
    taskbar_font_size: int = 9
    taskbar_show_download: bool = True
    taskbar_show_upload: bool = True
    taskbar_show_cpu: bool = True
    taskbar_show_ram: bool = True
    taskbar_background: str = "#1E1E1E"
    taskbar_foreground: str = "#FFFFFF"
    taskbar_download: str = "#6CCB5F"
    taskbar_upload: str = "#60CDFF"

    # Custom display labels
    label_download: str = "↓"
    label_upload: str = "↑"
    label_cpu: str = "CPU"
    label_ram: str = "RAM"

    # Startup & persistence
    start_with_windows: bool = True
    track_history: bool = True

    def apply_theme(self, theme_name: str) -> None:
        theme = THEMES.get(theme_name)
        if not theme:
            return
        for key, value in theme.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass(frozen=True)
class NetworkSnapshot:
    """Immutable network reading passed from the sampler to the UI."""

    download_bytes_per_second: float
    upload_bytes_per_second: float
    session_download_bytes: int
    session_upload_bytes: int
    active_adapter_label: str = "All active"


@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable reading of host CPU and RAM utilization."""

    cpu_percent: float
    memory_percent: float
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0


@dataclass(frozen=True)
class AdapterInfo:
    """Detailed status and counter metrics for a single network interface."""

    name: str
    is_up: bool
    is_virtual: bool
    speed_mbps: int
    mtu: int
    ipv4: str
    ipv6: str
    mac: str
    bytes_recv: int
    bytes_sent: int
    packets_recv: int
    packets_sent: int
    errin: int
    errout: int
    dropin: int
    dropout: int


@dataclass
class DailyTrafficRecord:
    """Persistent daily network traffic totals."""

    date: str
    download_bytes: int = 0
    upload_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return self.download_bytes + self.upload_bytes


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def format_rate(bytes_per_second: float, mode: str, precision: int = 1) -> str:
    """Format network throughput according to the selected TrafficMonitor unit mode."""
    speed = max(0.0, float(bytes_per_second))
    if mode == "Fixed KB/s":
        return f"{speed / 1000:.{precision}f} KB/s"
    if mode == "Fixed MB/s":
        return f"{speed / 1_000_000:.{max(precision, 2)}f} MB/s"
    if mode == "Fixed Mbps":
        return f"{(speed * 8) / 1_000_000:.{max(precision, 2)}f} Mbps"

    if mode in ("Bytes/s", "Auto (Bytes/s)"):
        value, units = speed, ("B/s", "KB/s", "MB/s", "GB/s")
    else:
        value, units = speed * 8, ("bps", "Kbps", "Mbps", "Gbps")

    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1
    if index == 0:
        return f"{value:.0f} {units[index]}"
    if value < 10:
        return f"{value:.{max(1, precision)}f} {units[index]}"
    if value < 100:
        return f"{value:.{min(1, precision)}f} {units[index]}"
    return f"{value:.0f} {units[index]}"


def format_total(byte_count: int) -> str:
    """Format cumulative data volume cleanly (B, KB, MB, GB, TB)."""
    value = float(max(0, byte_count))
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} {units[index]}"
    if index >= 3:
        return f"{value:.2f} {units[index]}"
    return f"{value:.1f} {units[index]}"
