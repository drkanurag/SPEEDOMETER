# Speedometer architecture

Speedometer is a local, single-process Windows desktop application modeled after
[TrafficMonitor](https://github.com/zhongyang219/TrafficMonitor). It deliberately
is not decomposed into networked microservices: a desktop speed monitor needs to
work offline, consume minimal memory and CPU, and avoid background servers,
ports, credentials, and deployment orchestration.

## Package & component boundaries

```text
Windows network counters ─> NetworkSampler ──────────┐
Windows CPU/RAM counters ─> SystemMetricsService ────┼─> SpeedometerApp
%APPDATA% settings <────── SettingsRepository ───────┤   ├─ MainOverlayWindow (floating skins)
%APPDATA% history <─────── TrafficHistoryRepository ─┤   ├─ TaskbarOverlayWindow (taskbar band)
Windows Run registry <──── WindowsStartupService ────┤   ├─ Options / Details / History dialogs
Win32 / DWM / Taskbar ──── WindowsPlatformService ───┘   └─ System tray + context menu
```

- `speedometer_app/models.py`: `Settings`, `THEMES`, `SKINS`, `UNIT_MODES`,
  immutable DTOs (`NetworkSnapshot`, `SystemSnapshot`, `AdapterInfo`,
  `DailyTrafficRecord`), and formatting helpers (`format_rate`, `format_total`).
- `speedometer_app/services.py`:
  - `NetworkSampler` owns byte-counter deltas, primary-adapter auto selection,
    session totals, and interface metadata (`adapter_details()`).
  - `SystemMetricsService` owns CPU and RAM utilization readings.
  - `SettingsRepository` and `TrafficHistoryRepository` own atomic JSON
    persistence under `%APPDATA%\Speedometer\`.
  - `WindowsStartupService` is the only boundary writing to the `Run` registry
    key.
  - `WindowsPlatformService` encapsulates DPI awareness, DWM rounded corners &
    borders, `WS_EX_TRANSPARENT` click-through, taskbar/tray rectangle lookups,
    Windows Light/Dark taskbar detection, and fullscreen auto-hide checks.
- `speedometer_app/ui_widgets.py`: `SparklineCanvas`, `UsageBar`, `ttk` theme
  configuration, and `create_app_icon`.
- `speedometer_app/overlays.py`: `MainOverlayWindow` and `TaskbarOverlayWindow`.
- `speedometer_app/dialogs.py`: `OptionsDialog`, `ConnectionDetailsDialog`, and
  `TrafficHistoryDialog`.
- `speedometer_app/app.py` and `speedometer.py`: `SpeedometerApp` coordinator
  and executable entry point.

## Reliability rules

1. Use `time.monotonic()` for elapsed time, never wall-clock time.
2. Clamp counter deltas at zero so adapter resets do not show negative traffic.
3. Treat settings, history, DWM, and startup calls as non-fatal.
4. Keep all state local to the current Windows user; no telemetry or network
   ports are opened.
5. Keep refresh work bounded: one `psutil` network read and one CPU/RAM read per
   selected interval (one second by default), with atomic file writes for
   settings and periodic traffic history checkpoints.
