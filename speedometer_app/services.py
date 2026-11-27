"""Local persistence, network/system sampling, and Windows platform integration."""

from __future__ import annotations

import csv
import ctypes
import ctypes.wintypes
import json
import os
import socket
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import psutil

from speedometer_app.models import (
    APP_NAME,
    CONFIG_DIR,
    CONFIG_FILE,
    HISTORY_FILE,
    RUN_KEY,
    AdapterInfo,
    DailyTrafficRecord,
    NetworkSnapshot,
    Settings,
    SystemSnapshot,
    clamp,
)

VIRTUAL_MARKERS = (
    "loopback",
    "vethernet",
    "hyper-v",
    "wsl",
    "docker",
    "vmware",
    "virtualbox",
    "npcap",
    "teredo",
    "isatap",
    "bluetooth",
)


class SettingsRepository:
    """Persistence boundary for user-owned JSON settings."""

    def __init__(self, config_file: Path = CONFIG_FILE) -> None:
        self.config_file = config_file

    def load(self) -> Settings:
        try:
            raw = json.loads(self.config_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return Settings()
            # Migrate legacy "Bytes/s" unit mode cleanly
            if raw.get("unit_mode") == "Bytes/s":
                raw["unit_mode"] = "Auto (Bytes/s)"
            schema_ver = int(raw.get("schema_version", 1))
            if schema_ver < 2:
                # Upgrade older installs to the new taskbar-sized layout
                if raw.get("dock_to_taskbar", True):
                    raw["skin"] = "Taskbar Strip"
                    raw["dock_side"] = "Right"
                raw["schema_version"] = 2
            allowed = {k: v for k, v in raw.items() if k in Settings.__dataclass_fields__}
            settings = Settings(**allowed)
            settings.interval = clamp(float(settings.interval), 0.25, 10.0)
            settings.opacity = clamp(float(settings.opacity), 0.30, 1.0)
            settings.font_size = int(clamp(int(settings.font_size), 8, 22))
            settings.taskbar_font_size = int(clamp(int(settings.taskbar_font_size), 7, 14))
            return settings
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.config_file.with_suffix(".tmp")
            from dataclasses import asdict

            tmp_file.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
            tmp_file.replace(self.config_file)
        except OSError:
            pass


class TrafficHistoryRepository:
    """Tracks and persists daily cumulative network traffic in %APPDATA%."""

    def __init__(self, history_file: Path = HISTORY_FILE) -> None:
        self.history_file = history_file
        self._records: dict[str, DailyTrafficRecord] = {}
        self.load()

    def load(self) -> None:
        self._records.clear()
        try:
            raw = json.loads(self.history_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for day_str, entry in raw.items():
                    if isinstance(entry, dict):
                        self._records[day_str] = DailyTrafficRecord(
                            date=day_str,
                            download_bytes=max(0, int(entry.get("download_bytes", 0))),
                            upload_bytes=max(0, int(entry.get("upload_bytes", 0))),
                        )
        except (OSError, ValueError, TypeError):
            pass

    def add_bytes(self, down_bytes: int, up_bytes: int, day: date | None = None) -> None:
        if down_bytes <= 0 and up_bytes <= 0:
            return
        day_str = (day or date.today()).isoformat()
        rec = self._records.get(day_str)
        if rec is None:
            rec = DailyTrafficRecord(date=day_str)
            self._records[day_str] = rec
        rec.download_bytes += max(0, down_bytes)
        rec.upload_bytes += max(0, up_bytes)

    def save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.history_file.with_suffix(".tmp")
            payload = {
                day: {"download_bytes": rec.download_bytes, "upload_bytes": rec.upload_bytes}
                for day, rec in sorted(self._records.items())
            }
            tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_file.replace(self.history_file)
        except OSError:
            pass

    def records_descending(self) -> list[DailyTrafficRecord]:
        return [self._records[k] for k in sorted(self._records.keys(), reverse=True)]

    def recent_days(self, days: int = 14) -> list[DailyTrafficRecord]:
        today = date.today()
        result: list[DailyTrafficRecord] = []
        for offset in range(days - 1, -1, -1):
            d = (today - timedelta(days=offset)).isoformat()
            result.append(self._records.get(d, DailyTrafficRecord(date=d)))
        return result

    def summary(self) -> dict[str, tuple[int, int]]:
        """Return (download_bytes, upload_bytes) for today, yesterday, week, month, all_time."""
        today = date.today()
        today_str = today.isoformat()
        yesterday_str = (today - timedelta(days=1)).isoformat()
        week_cutoff = (today - timedelta(days=6)).isoformat()
        month_prefix = today.strftime("%Y-%m")

        def sum_matching(pred) -> tuple[int, int]:
            down = up = 0
            for k, rec in self._records.items():
                if pred(k):
                    down += rec.download_bytes
                    up += rec.upload_bytes
            return down, up

        return {
            "today": sum_matching(lambda k: k == today_str),
            "yesterday": sum_matching(lambda k: k == yesterday_str),
            "week": sum_matching(lambda k: k >= week_cutoff),
            "month": sum_matching(lambda k: k.startswith(month_prefix)),
            "all_time": sum_matching(lambda _k: True),
        }

    def clear(self) -> None:
        self._records.clear()
        self.save()

    def export_csv(self, destination: Path) -> None:
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Date", "Download (Bytes)", "Upload (Bytes)", "Total (Bytes)"])
            for rec in self.records_descending():
                writer.writerow([rec.date, rec.download_bytes, rec.upload_bytes, rec.total_bytes])


class WindowsStartupService:
    """Integration boundary for the per-user Windows Run registry key."""

    @staticmethod
    def apply(enabled: bool, entry_script: Path | None = None) -> None:
        try:
            import winreg

            target = entry_script or Path(sys.argv[0]).resolve()
            command = f'"{sys.executable}"' if getattr(sys, "frozen", False) else f'"{sys.executable}" "{target}"'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
        except OSError:
            pass


class NetworkSampler:
    """Computes live network throughput using monotonic timestamps and byte counters."""

    AUTO_ALL = "All active adapters"
    AUTO_PRIMARY = "Auto (Primary active)"

    def __init__(self, adapter: str, include_virtual: bool = False) -> None:
        self.adapter = adapter
        self.include_virtual = include_virtual
        self.total_down = 0
        self.total_up = 0
        self._resolved_primary: str | None = None
        self.previous = self._counts()
        self.previous_time = time.monotonic()

    @staticmethod
    def is_virtual(name: str) -> bool:
        lowered = name.lower()
        return any(marker in lowered for marker in VIRTUAL_MARKERS)

    @classmethod
    def adapters(cls, include_virtual: bool = False) -> list[str]:
        stats = psutil.net_if_stats()
        names = []
        for name, state in stats.items():
            if not state.isup:
                continue
            if not include_virtual and cls.is_virtual(name):
                continue
            names.append(name)
        return sorted(names)

    def _pick_primary_adapter(self, counters: dict) -> list[str]:
        candidates = self.adapters(include_virtual=self.include_virtual)
        if not candidates:
            return []
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        def score(name: str) -> tuple[int, int, int]:
            has_ip = any(
                a.family == socket.AF_INET and not a.address.startswith("169.254.") and a.address != "127.0.0.1"
                for a in addrs.get(name, [])
            )
            c = counters.get(name)
            traffic = (c.bytes_recv + c.bytes_sent) if c else 0
            speed = stats[name].speed if name in stats else 0
            return (1 if has_ip else 0, traffic, speed)

        best = max(candidates, key=score)
        self._resolved_primary = best
        return [best]

    def _target_names(self, counters: dict) -> list[str]:
        if self.adapter == self.AUTO_ALL:
            return self.adapters(include_virtual=self.include_virtual)
        if self.adapter == self.AUTO_PRIMARY:
            return self._pick_primary_adapter(counters)
        return [self.adapter]

    def _counts(self) -> tuple[int, int]:
        counters = psutil.net_io_counters(pernic=True) or {}
        names = self._target_names(counters)
        received = sent = 0
        for name in names:
            data = counters.get(name)
            if data:
                received += data.bytes_recv
                sent += data.bytes_sent
        return received, sent

    def change_adapter(self, adapter: str, include_virtual: bool | None = None) -> None:
        self.adapter = adapter
        if include_virtual is not None:
            self.include_virtual = include_virtual
        self._resolved_primary = None
        self.previous = self._counts()
        self.previous_time = time.monotonic()
        self.total_down = self.total_up = 0

    def reset_totals(self) -> None:
        self.total_down = 0
        self.total_up = 0

    def active_label(self) -> str:
        if self.adapter == self.AUTO_PRIMARY:
            return self._resolved_primary or "Auto"
        if self.adapter == self.AUTO_ALL:
            active = self.adapters(include_virtual=self.include_virtual)
            if len(active) == 1:
                return active[0]
            return f"All active ({len(active)})"
        return self.adapter

    def sample(self) -> tuple[NetworkSnapshot, int, int]:
        """Return (NetworkSnapshot, delta_down_bytes, delta_up_bytes)."""
        now = time.monotonic()
        current = self._counts()
        elapsed = max(now - self.previous_time, 0.01)
        delta_down = max(current[0] - self.previous[0], 0)
        delta_up = max(current[1] - self.previous[1], 0)
        down_rate = delta_down / elapsed
        up_rate = delta_up / elapsed
        self.total_down += delta_down
        self.total_up += delta_up
        self.previous, self.previous_time = current, now
        snapshot = NetworkSnapshot(
            download_bytes_per_second=down_rate,
            upload_bytes_per_second=up_rate,
            session_download_bytes=self.total_down,
            session_upload_bytes=self.total_up,
            active_adapter_label=self.active_label(),
        )
        return snapshot, delta_down, delta_up

    @classmethod
    def adapter_details(cls) -> list[AdapterInfo]:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        counters = psutil.net_io_counters(pernic=True)
        items: list[AdapterInfo] = []
        for name in sorted(stats.keys(), key=lambda n: (not stats[n].isup, cls.is_virtual(n), n.lower())):
            st = stats[name]
            c = counters.get(name)
            ipv4 = ipv6 = mac = "-"
            for addr in addrs.get(name, []):
                if addr.family == socket.AF_INET and ipv4 == "-":
                    ipv4 = f"{addr.address} / {addr.netmask or ''}".rstrip(" /")
                elif addr.family == socket.AF_INET6 and ipv6 == "-":
                    ipv6 = addr.address.split("%")[0]
                elif addr.family == getattr(psutil, "AF_LINK", -1) and mac == "-":
                    mac = addr.address
            items.append(
                AdapterInfo(
                    name=name,
                    is_up=st.isup,
                    is_virtual=cls.is_virtual(name),
                    speed_mbps=st.speed,
                    mtu=st.mtu,
                    ipv4=ipv4,
                    ipv6=ipv6,
                    mac=mac,
                    bytes_recv=c.bytes_recv if c else 0,
                    bytes_sent=c.bytes_sent if c else 0,
                    packets_recv=c.packets_recv if c else 0,
                    packets_sent=c.packets_sent if c else 0,
                    errin=c.errin if c else 0,
                    errout=c.errout if c else 0,
                    dropin=c.dropin if c else 0,
                    dropout=c.dropout if c else 0,
                )
            )
        return items


class SystemMetricsService:
    """Provides inexpensive CPU and RAM snapshots at the UI refresh cadence."""

    def __init__(self) -> None:
        # Prime psutil's non-blocking CPU percent baseline so the first UI reading is real.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    @staticmethod
    def sample(power_watts: float | None = None) -> SystemSnapshot:
        mem = psutil.virtual_memory()
        gib = 1024 ** 3
        return SystemSnapshot(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=mem.percent,
            memory_used_gb=mem.used / gib,
            memory_total_gb=mem.total / gib,
            power_watts=power_watts,
        )


class PowerMetricsService:
    """Reads real-time laptop power consumption strictly in Watts (W).

    Uses Windows PDH Power Meter / Energy Meter (RAPL) counters via ctypes and
    Win32 CallNtPowerInformation(SystemBatteryState) when discharging on battery.
    """

    _PDH_FMT_DOUBLE = 0x00000200
    _BATTERY_UNKNOWN_RATE = -2147483648  # 0x80000000

    class _PDH_FMT_COUNTERVALUE(ctypes.Structure):
        _fields_ = [
            ("CStatus", ctypes.wintypes.DWORD),
            ("doubleValue", ctypes.c_double),
        ]

    class _SYSTEM_BATTERY_STATE(ctypes.Structure):
        _fields_ = [
            ("AcOnLine", ctypes.c_ubyte),
            ("BatteryPresent", ctypes.c_ubyte),
            ("Charging", ctypes.c_ubyte),
            ("Discharging", ctypes.c_ubyte),
            ("Spare1", ctypes.c_ubyte * 3),
            ("Tag", ctypes.c_ubyte),
            ("MaxCapacity", ctypes.wintypes.DWORD),
            ("RemainingCapacity", ctypes.wintypes.DWORD),
            ("Rate", ctypes.c_long),
            ("EstimatedTime", ctypes.wintypes.DWORD),
            ("DefaultAlert1", ctypes.wintypes.DWORD),
            ("DefaultAlert2", ctypes.wintypes.DWORD),
        ]

    def __init__(self) -> None:
        self._pdh = None
        self._query: ctypes.c_void_p | None = None
        self._power_meter_handles: list[ctypes.c_void_p] = []
        self._energy_meter_handles: list[ctypes.c_void_p] = []
        self._initialized = False

    def _ensure_pdh(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        try:
            pdh = ctypes.windll.pdh
            wt = ctypes.wintypes
            pdh.PdhOpenQueryW.argtypes = [wt.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            pdh.PdhOpenQueryW.restype = wt.LONG
            pdh.PdhAddEnglishCounterW.argtypes = [
                ctypes.c_void_p,
                wt.LPCWSTR,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            pdh.PdhAddEnglishCounterW.restype = wt.LONG
            pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
            pdh.PdhCollectQueryData.restype = wt.LONG
            pdh.PdhGetFormattedCounterValue.argtypes = [
                ctypes.c_void_p,
                wt.DWORD,
                ctypes.POINTER(wt.DWORD),
                ctypes.POINTER(self._PDH_FMT_COUNTERVALUE),
            ]
            pdh.PdhGetFormattedCounterValue.restype = wt.LONG
            pdh.PdhExpandWildCardPathW.argtypes = [
                wt.LPCWSTR,
                wt.LPCWSTR,
                wt.LPWSTR,
                ctypes.POINTER(wt.DWORD),
                wt.DWORD,
            ]
            pdh.PdhExpandWildCardPathW.restype = wt.LONG
            pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
            pdh.PdhCloseQuery.restype = wt.LONG

            query = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, None, ctypes.byref(query)) != 0:
                return
            self._pdh = pdh
            self._query = query

            for path in self._select_power_meter_paths():
                h = ctypes.c_void_p()
                if pdh.PdhAddEnglishCounterW(query, path, None, ctypes.byref(h)) == 0:
                    self._power_meter_handles.append(h)

            for path in self._select_energy_meter_paths():
                h = ctypes.c_void_p()
                if pdh.PdhAddEnglishCounterW(query, path, None, ctypes.byref(h)) == 0:
                    self._energy_meter_handles.append(h)

            if self._power_meter_handles or self._energy_meter_handles:
                pdh.PdhCollectQueryData(query)
        except Exception:
            self.close()

    def _expand(self, pattern: str) -> list[str]:
        if not self._pdh:
            return []
        try:
            buf_len = ctypes.wintypes.DWORD(0)
            self._pdh.PdhExpandWildCardPathW(None, pattern, None, ctypes.byref(buf_len), 0)
            if buf_len.value == 0:
                return []
            buf = ctypes.create_unicode_buffer(buf_len.value)
            res = self._pdh.PdhExpandWildCardPathW(None, pattern, buf, ctypes.byref(buf_len), 0)
            if res != 0:
                return []
            raw = ctypes.wstring_at(buf, buf_len.value)
            return [p for p in raw.split("\x00") if p]
        except Exception:
            return []

    def _select_power_meter_paths(self) -> list[str]:
        paths = self._expand(r"\Power Meter(*)\Power")
        totals = [p for p in paths if "(_Total)" in p]
        return totals or [p for p in paths if "(_Total)" not in p]

    def _select_energy_meter_paths(self) -> list[str]:
        paths = self._expand(r"\Energy Meter(*)\Power")
        pkg = [p for p in paths if "_PKG)" in p.upper()]
        if pkg:
            return pkg
        return [p for p in paths if "(_Total)" not in p]

    def _sum_handles_mw(self, handles: list[ctypes.c_void_p]) -> float:
        if not self._pdh or not handles:
            return 0.0
        total_mw = 0.0
        val = self._PDH_FMT_COUNTERVALUE()
        ctype = ctypes.wintypes.DWORD()
        for h in handles:
            if (
                self._pdh.PdhGetFormattedCounterValue(
                    h, self._PDH_FMT_DOUBLE, ctypes.byref(ctype), ctypes.byref(val)
                )
                == 0
            ):
                if val.CStatus == 0 and val.doubleValue > 0:
                    total_mw += val.doubleValue
        return total_mw

    @classmethod
    def _battery_discharge_watts(cls) -> float | None:
        try:
            sbs = cls._SYSTEM_BATTERY_STATE()
            status = ctypes.windll.powrprof.CallNtPowerInformation(
                5, None, 0, ctypes.byref(sbs), ctypes.sizeof(sbs)
            )
            if status == 0 and sbs.BatteryPresent and not sbs.AcOnLine and sbs.Discharging:
                if sbs.Rate != 0 and sbs.Rate != cls._BATTERY_UNKNOWN_RATE:
                    return abs(sbs.Rate) / 1000.0
        except Exception:
            pass
        return None

    def sample_watts(self) -> float | None:
        """Return real-time power draw in Watts, or None if no sensor is available."""
        self._ensure_pdh()
        pm_mw = 0.0
        em_mw = 0.0
        if self._pdh and self._query and (self._power_meter_handles or self._energy_meter_handles):
            try:
                if self._pdh.PdhCollectQueryData(self._query) == 0:
                    pm_mw = self._sum_handles_mw(self._power_meter_handles)
                    em_mw = self._sum_handles_mw(self._energy_meter_handles)
            except Exception:
                pass

        if pm_mw > 0:
            return pm_mw / 1000.0

        battery_w = self._battery_discharge_watts()
        if battery_w is not None and battery_w > 0:
            return battery_w

        if em_mw > 0:
            return em_mw / 1000.0
        return None

    def close(self) -> None:
        if self._pdh and self._query:
            try:
                self._pdh.PdhCloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._power_meter_handles.clear()
        self._energy_meter_handles.clear()


class WindowsPlatformService:
    """Encapsulates Win32/DWM window styling, DPI, taskbar geometry, and fullscreen checks."""

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    GA_ROOT = 2

    HWND_TOPMOST = ctypes.wintypes.HWND(-1)
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010

    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWA_BORDER_COLOR = 34
    DWMWCP_ROUND = 2
    DWMWCP_ROUNDSMALL = 3

    _signatures_configured = False

    @classmethod
    def _configure_win32_signatures(cls) -> None:
        if cls._signatures_configured:
            return
        cls._signatures_configured = True
        try:
            u32 = ctypes.windll.user32
            u32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
            u32.GetAncestor.restype = ctypes.wintypes.HWND
            u32.GetForegroundWindow.argtypes = []
            u32.GetForegroundWindow.restype = ctypes.wintypes.HWND
            u32.MonitorFromWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
            u32.MonitorFromWindow.restype = ctypes.wintypes.HMONITOR
            u32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
            u32.GetWindowRect.restype = ctypes.wintypes.BOOL
            u32.GetClassNameW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
            u32.GetClassNameW.restype = ctypes.c_int
            u32.SetWindowPos.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.wintypes.UINT,
            ]
            u32.SetWindowPos.restype = ctypes.wintypes.BOOL
            u32.FindWindowW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR]
            u32.FindWindowW.restype = ctypes.wintypes.HWND
            u32.FindWindowExW.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.wintypes.HWND,
                ctypes.wintypes.LPCWSTR,
                ctypes.wintypes.LPCWSTR,
            ]
            u32.FindWindowExW.restype = ctypes.wintypes.HWND
        except Exception:
            pass

    @staticmethod
    def enable_dpi_awareness() -> None:
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass

    @classmethod
    def root_hwnd(cls, widget) -> int:
        cls._configure_win32_signatures()
        try:
            hwnd = int(widget.winfo_id())
            root = ctypes.windll.user32.GetAncestor(ctypes.wintypes.HWND(hwnd), cls.GA_ROOT)
            return int(root) if root else hwnd
        except Exception:
            return 0

    @classmethod
    def apply_rounded_corners(cls, widget, small: bool = False, border_hex: str | None = None) -> None:
        hwnd = cls.root_hwnd(widget)
        if not hwnd:
            return
        try:
            pref = ctypes.c_int(cls.DWMWCP_ROUNDSMALL if small else cls.DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.wintypes.HWND(hwnd), cls.DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref)
            )
            if border_hex and border_hex.startswith("#") and len(border_hex) == 7:
                r = int(border_hex[1:3], 16)
                g = int(border_hex[3:5], 16)
                b = int(border_hex[5:7], 16)
                colorref = ctypes.c_int((b << 16) | (g << 8) | r)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.wintypes.HWND(hwnd), cls.DWMWA_BORDER_COLOR, ctypes.byref(colorref), ctypes.sizeof(colorref)
                )
        except Exception:
            pass

    @classmethod
    def apply_dark_titlebar(cls, widget, dark: bool = True) -> None:
        hwnd = cls.root_hwnd(widget)
        if not hwnd:
            return
        try:
            val = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.wintypes.HWND(hwnd), cls.DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

    @classmethod
    def _get_exstyle(cls, hwnd: int) -> int:
        u32 = ctypes.windll.user32
        if hasattr(u32, "GetWindowLongPtrW"):
            u32.GetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
            u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            return int(u32.GetWindowLongPtrW(ctypes.wintypes.HWND(hwnd), cls.GWL_EXSTYLE))
        return int(u32.GetWindowLongW(ctypes.wintypes.HWND(hwnd), cls.GWL_EXSTYLE))

    @classmethod
    def _set_exstyle(cls, hwnd: int, style: int) -> None:
        u32 = ctypes.windll.user32
        if hasattr(u32, "SetWindowLongPtrW"):
            u32.SetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            u32.SetWindowLongPtrW(ctypes.wintypes.HWND(hwnd), cls.GWL_EXSTYLE, style)
        else:
            u32.SetWindowLongW(ctypes.wintypes.HWND(hwnd), cls.GWL_EXSTYLE, style)

    @classmethod
    def set_tool_window(cls, widget) -> None:
        hwnd = cls.root_hwnd(widget)
        if not hwnd:
            return
        try:
            style = cls._get_exstyle(hwnd)
            cls._set_exstyle(hwnd, style | cls.WS_EX_TOOLWINDOW)
        except Exception:
            pass

    @classmethod
    def set_mouse_penetrate(cls, widget, enabled: bool) -> None:
        hwnd = cls.root_hwnd(widget)
        if not hwnd:
            return
        try:
            style = cls._get_exstyle(hwnd)
            if enabled:
                style = style | cls.WS_EX_LAYERED | cls.WS_EX_TRANSPARENT
            else:
                style = style & ~cls.WS_EX_TRANSPARENT
            cls._set_exstyle(hwnd, style)
        except Exception:
            pass

    @classmethod
    def keep_topmost(cls, widget) -> None:
        """Raise window above the Windows taskbar without stealing input focus."""
        hwnd = cls.root_hwnd(widget)
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetWindowPos(
                ctypes.wintypes.HWND(hwnd),
                cls.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                cls.SWP_NOMOVE | cls.SWP_NOSIZE | cls.SWP_NOACTIVATE,
            )
        except Exception:
            pass

    @classmethod
    def taskbar_rect(cls) -> tuple[int, int, int, int] | None:
        """Return (left, top, right, bottom) of the primary Windows taskbar."""
        cls._configure_win32_signatures()

        class APPBARDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.DWORD),
                ("hWnd", ctypes.wintypes.HWND),
                ("uCallbackMessage", ctypes.wintypes.UINT),
                ("uEdge", ctypes.wintypes.UINT),
                ("rc", ctypes.wintypes.RECT),
                ("lParam", ctypes.wintypes.LPARAM),
            ]

        try:
            data = APPBARDATA()
            data.cbSize = ctypes.sizeof(data)
            if ctypes.windll.shell32.SHAppBarMessage(5, ctypes.byref(data)):
                rc = data.rc
                if rc.right > rc.left and rc.bottom > rc.top:
                    return (rc.left, rc.top, rc.right, rc.bottom)
        except Exception:
            pass

        try:
            u32 = ctypes.windll.user32
            tray = u32.FindWindowW("Shell_TrayWnd", None)
            if tray:
                rc = ctypes.wintypes.RECT()
                if u32.GetWindowRect(ctypes.wintypes.HWND(tray), ctypes.byref(rc)) and rc.right > rc.left:
                    return (rc.left, rc.top, rc.right, rc.bottom)
        except Exception:
            pass
        return None

    @classmethod
    def tray_notify_rect(cls) -> tuple[int, int, int, int] | None:
        """Return the Windows notification-area (clock/tray) rectangle to avoid overlap."""
        cls._configure_win32_signatures()
        try:
            u32 = ctypes.windll.user32
            tray = u32.FindWindowW("Shell_TrayWnd", None)
            if not tray:
                return None
            notify = u32.FindWindowExW(ctypes.wintypes.HWND(tray), None, "TrayNotifyWnd", None)
            if notify:
                rc = ctypes.wintypes.RECT()
                if u32.GetWindowRect(ctypes.wintypes.HWND(notify), ctypes.byref(rc)) and rc.right > rc.left:
                    return (rc.left, rc.top, rc.right, rc.bottom)
        except Exception:
            pass
        return None

    @staticmethod
    def work_area() -> tuple[int, int, int, int]:
        rect = ctypes.wintypes.RECT()
        try:
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
            if rect.right > rect.left and rect.bottom > rect.top:
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            pass
        return (0, 0, 1920, 1040)

    @staticmethod
    def is_system_light_theme() -> bool:
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
                return bool(val)
        except Exception:
            return False

    @classmethod
    def is_foreground_fullscreen(cls, own_hwnds: set[int]) -> bool:
        """Detect whether another foreground application covers its entire monitor."""
        cls._configure_win32_signatures()
        try:
            u32 = ctypes.windll.user32
            fg = u32.GetForegroundWindow()
            if not fg or int(fg) in own_hwnds:
                return False
            fg_hwnd = ctypes.wintypes.HWND(fg)
            cls_buf = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(fg_hwnd, cls_buf, 64)
            if cls_buf.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
                return False

            win_rect = ctypes.wintypes.RECT()
            if not u32.GetWindowRect(fg_hwnd, ctypes.byref(win_rect)):
                return False

            monitor = u32.MonitorFromWindow(fg_hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            if not monitor:
                return False

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD),
                ]

            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            u32.GetMonitorInfoW.argtypes = [ctypes.wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
            u32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL
            if not u32.GetMonitorInfoW(ctypes.wintypes.HMONITOR(monitor), ctypes.byref(mi)):
                return False
            m = mi.rcMonitor
            return (
                win_rect.left <= m.left
                and win_rect.top <= m.top
                and win_rect.right >= m.right
                and win_rect.bottom >= m.bottom
            )
        except Exception:
            return False

    @staticmethod
    def open_config_folder(folder: Path = CONFIG_DIR) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception:
            try:
                subprocess.Popen(["explorer", str(folder)])
            except Exception:
                pass
