"""Main Speedometer coordinator wiring services, overlays, tray, context menu, and dialogs."""

from __future__ import annotations

import tkinter as tk
import traceback

import pystray
from PIL import ImageTk

from speedometer_app.dialogs import ConnectionDetailsDialog, OptionsDialog, TrafficHistoryDialog
from speedometer_app.models import (
    APP_NAME,
    CONFIG_DIR,
    SKINS,
    NetworkSnapshot,
    Settings,
    SystemSnapshot,
    format_rate,
    format_watts,
)
from speedometer_app.overlays import MainOverlayWindow, TaskbarOverlayWindow
from speedometer_app.services import (
    NetworkSampler,
    PowerMetricsService,
    SettingsRepository,
    SystemMetricsService,
    TrafficHistoryRepository,
    WindowsPlatformService,
    WindowsStartupService,
)
from speedometer_app.ui_widgets import configure_ttk_theme, create_app_icon


class SpeedometerApp:
    """Orchestrates sampling, overlays, system tray, context menu, and dialogs."""

    def __init__(self) -> None:
        WindowsPlatformService.enable_dpi_awareness()

        self.settings_repository = SettingsRepository()
        self.history_repository = TrafficHistoryRepository()
        self.startup_service = WindowsStartupService()
        self.settings = self.settings_repository.load()
        self.sampler = NetworkSampler(self.settings.adapter, self.settings.show_virtual_adapters)
        self.system_metrics = SystemMetricsService()
        self.power_metrics = PowerMetricsService()

        self._ticks_since_history_save = 0
        self._options_dialog: OptionsDialog | None = None
        self._details_dialog: ConnectionDetailsDialog | None = None
        self._history_dialog: TrafficHistoryDialog | None = None
        self._context_menu: tk.Menu | None = None

        self.root = tk.Tk()
        self.root.withdraw()
        configure_ttk_theme(self.root)

        self._icon_image = create_app_icon(64)
        self._tk_icon = ImageTk.PhotoImage(self._icon_image)
        try:
            self.root.iconphoto(True, self._tk_icon)
        except tk.TclError:
            pass

        self.main_overlay = MainOverlayWindow(
            root=self.root,
            settings=self.settings,
            on_context_menu=self.show_context_menu,
            on_open_options=self.open_options,
            on_position_changed=self._on_main_position_changed,
        )
        self.taskbar_overlay = TaskbarOverlayWindow(
            root=self.root,
            settings=self.settings,
            on_context_menu=self.show_context_menu,
            on_open_options=self.open_options,
        )

        self.root.protocol("WM_DELETE_WINDOW", self.toggle_main_window)
        self.startup_service.apply(self.settings.start_with_windows)

        self._create_tray()
        self.root.after(50, self.tick)

    def _create_tray(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                "Show Main Window",
                self.toggle_main_window,
                checked=lambda _item: self.settings.show_main_window,
                default=True,
            ),
            pystray.MenuItem(
                "Show Taskbar Window",
                self.toggle_taskbar_window,
                checked=lambda _item: self.settings.show_taskbar_window,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Always on Top",
                self.toggle_always_on_top,
                checked=lambda _item: self.settings.always_on_top,
            ),
            pystray.MenuItem(
                "Lock Window Position",
                self.toggle_lock_position,
                checked=lambda _item: self.settings.lock_position,
            ),
            pystray.MenuItem(
                "Mouse Penetrate (Click-through)",
                self.toggle_mouse_penetrate,
                checked=lambda _item: self.settings.mouse_penetrate,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Connection Details…", self.open_connection_details),
            pystray.MenuItem("Historical Traffic Statistics…", self.open_traffic_history),
            pystray.MenuItem("Options…", self.open_options),
            pystray.MenuItem("Reset Session Totals", self.reset_totals),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.exit),
        )
        self.tray = pystray.Icon(APP_NAME, self._icon_image, APP_NAME, menu)
        self.tray.run_detached()

    def show_context_menu(self, event: tk.Event) -> None:
        if self._context_menu is not None:
            try:
                self._context_menu.destroy()
            except tk.TclError:
                pass

        menu = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 9))
        self._context_menu = menu

        # Select Network Connection submenu (TrafficMonitor style)
        net_menu = tk.Menu(menu, tearoff=0, font=("Segoe UI", 9))
        adapter_var = tk.StringVar(value=self.settings.adapter)
        choices = [NetworkSampler.AUTO_ALL, NetworkSampler.AUTO_PRIMARY] + self.sampler.adapters(
            include_virtual=self.settings.show_virtual_adapters
        )
        for name in choices:
            net_menu.add_radiobutton(
                label=name,
                variable=adapter_var,
                value=name,
                command=lambda n=name: self._select_adapter(n),
            )
        menu.add_cascade(label="Select Network Connection", menu=net_menu)

        # Skin submenu
        skin_menu = tk.Menu(menu, tearoff=0, font=("Segoe UI", 9))
        skin_var = tk.StringVar(value=self.settings.skin)
        for skin_name in SKINS:
            skin_menu.add_radiobutton(
                label=skin_name,
                variable=skin_var,
                value=skin_name,
                command=lambda sn=skin_name: self._select_skin(sn),
            )
        menu.add_cascade(label="Window Skin", menu=skin_menu)
        menu.add_command(label="Align to Taskbar", command=self._snap_to_taskbar)

        # Quick Display Settings submenu
        disp_menu = tk.Menu(menu, tearoff=0, font=("Segoe UI", 9))
        self._add_bool_menu_item(disp_menu, "Show Live Sparkline", "show_sparkline")
        self._add_bool_menu_item(disp_menu, "Show CPU & RAM", "show_system_stats")
        self._add_bool_menu_item(disp_menu, "Show Power Usage (W)", "show_power_watts")
        self._add_bool_menu_item(disp_menu, "Show Taskbar Power (W)", "taskbar_show_power_watts")
        self._add_bool_menu_item(disp_menu, "Show Session Totals", "show_totals")
        self._add_bool_menu_item(disp_menu, "Show Adapter Header", "show_adapter_name")
        menu.add_cascade(label="Display Settings", menu=disp_menu)

        menu.add_separator()
        self._add_bool_menu_item(menu, "Show Main Window", "show_main_window")
        self._add_bool_menu_item(menu, "Show Taskbar Window", "show_taskbar_window")
        menu.add_separator()
        self._add_bool_menu_item(menu, "Always on Top", "always_on_top")
        self._add_bool_menu_item(menu, "Lock Window Position", "lock_position")
        self._add_bool_menu_item(menu, "Mouse Penetrate (Click-through)", "mouse_penetrate")
        self._add_bool_menu_item(menu, "Auto-Hide on Fullscreen", "auto_hide_fullscreen")
        menu.add_separator()
        menu.add_command(label="Connection Details…", command=self.open_connection_details)
        menu.add_command(label="Historical Traffic Statistics…", command=self.open_traffic_history)
        menu.add_command(label="Options…", command=self.open_options)
        menu.add_command(label="Reset Session Totals", command=self.reset_totals)
        menu.add_separator()
        menu.add_command(label="Exit", command=self.exit)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _add_bool_menu_item(self, menu: tk.Menu, label: str, attr: str) -> None:
        var = tk.BooleanVar(value=bool(getattr(self.settings, attr)))
        menu.add_checkbutton(
            label=label,
            variable=var,
            command=lambda: self._toggle_setting(attr),
        )

    def _toggle_setting(self, attr: str) -> None:
        setattr(self.settings, attr, not bool(getattr(self.settings, attr)))
        self.apply_settings(self.settings)

    def _select_adapter(self, adapter_name: str) -> None:
        self.settings.adapter = adapter_name
        self.apply_settings(self.settings)

    def _select_skin(self, skin_name: str) -> None:
        self.settings.skin = skin_name
        self.settings.compact = False
        self.apply_settings(self.settings)

    def _snap_to_taskbar(self) -> None:
        self.settings.dock_to_taskbar = True
        self.settings.window_x = None
        self.settings.window_y = None
        self.apply_settings(self.settings)

    def _on_main_position_changed(self, x: int, y: int) -> None:
        self.settings.dock_to_taskbar = False
        self.settings.window_x = x
        self.settings.window_y = y
        self.settings_repository.save(self.settings)

    def apply_settings(self, new_settings: Settings) -> None:
        adapter_changed = (
            new_settings.adapter != self.settings.adapter
            or new_settings.show_virtual_adapters != self.settings.show_virtual_adapters
        )
        self.settings = new_settings
        self.main_overlay.settings = new_settings
        self.taskbar_overlay.settings = new_settings

        if adapter_changed:
            self.sampler.change_adapter(new_settings.adapter, new_settings.show_virtual_adapters)

        self.startup_service.apply(new_settings.start_with_windows)
        self.settings_repository.save(new_settings)

        self.main_overlay.rebuild()
        self.main_overlay.apply_position()
        self.taskbar_overlay.rebuild()

    def tick(self) -> None:
        delay_ms = max(250, int(self.settings.interval * 1000))
        try:
            network, delta_down, delta_up = self.sampler.sample()
            power_w = (
                self.power_metrics.sample_watts()
                if (self.settings.show_power_watts or self.settings.taskbar_show_power_watts)
                else None
            )
            system = self.system_metrics.sample(power_watts=power_w)

            if self.settings.track_history:
                self.history_repository.add_bytes(delta_down, delta_up)
                self._ticks_since_history_save += 1
                if self._ticks_since_history_save >= 30:
                    self.history_repository.save()
                    self._ticks_since_history_save = 0

            if self.settings.auto_hide_fullscreen:
                own = {
                    WindowsPlatformService.root_hwnd(self.root),
                    WindowsPlatformService.root_hwnd(self.taskbar_overlay.win),
                }
                is_fs = WindowsPlatformService.is_foreground_fullscreen({h for h in own if h})
                self.main_overlay.set_fullscreen_hidden(is_fs)
                self.taskbar_overlay.set_fullscreen_hidden(is_fs)
            else:
                self.main_overlay.set_fullscreen_hidden(False)
                self.taskbar_overlay.set_fullscreen_hidden(False)

            self.main_overlay.update_data(network, system)
            self.taskbar_overlay.update_data(network, system)
            self.main_overlay.ensure_topmost()
            self.taskbar_overlay.ensure_topmost()
            self._update_tray_tooltip(network, system)
        except Exception:
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                (CONFIG_DIR / "speedometer.log").write_text(traceback.format_exc(), encoding="utf-8")
            except OSError:
                pass
        finally:
            self.root.after(delay_ms, self.tick)

    def _update_tray_tooltip(self, network: NetworkSnapshot, system: SystemSnapshot) -> None:
        down = format_rate(network.download_bytes_per_second, self.settings.unit_mode, self.settings.precision)
        up = format_rate(network.upload_bytes_per_second, self.settings.unit_mode, self.settings.precision)
        sys_line = f"CPU {system.cpu_percent:.0f}% | RAM {system.memory_percent:.0f}%"
        if self.settings.show_power_watts or self.settings.taskbar_show_power_watts:
            sys_line += f" | {format_watts(system.power_watts)}"
        tip = f"{APP_NAME}\n↓ {down} | ↑ {up}\n{sys_line}"
        try:
            self.tray.title = tip[:120]
        except Exception:
            pass

    def toggle_main_window(self, *_args) -> None:
        self.root.after(0, lambda: self._toggle_setting("show_main_window"))

    def toggle_taskbar_window(self, *_args) -> None:
        self.root.after(0, lambda: self._toggle_setting("show_taskbar_window"))

    def toggle_always_on_top(self, *_args) -> None:
        self.root.after(0, lambda: self._toggle_setting("always_on_top"))

    def toggle_lock_position(self, *_args) -> None:
        self.root.after(0, lambda: self._toggle_setting("lock_position"))

    def toggle_mouse_penetrate(self, *_args) -> None:
        self.root.after(0, lambda: self._toggle_setting("mouse_penetrate"))

    def reset_totals(self, *_args) -> None:
        self.root.after(0, self.sampler.reset_totals)

    def open_options(self, *_args) -> None:
        self.root.after(0, self._open_options_ui)

    def _open_options_ui(self) -> None:
        if self._options_dialog and self._options_dialog.win.winfo_exists():
            self._options_dialog.show()
            return
        self._options_dialog = OptionsDialog(
            parent=self.root,
            settings=self.settings,
            sampler=self.sampler,
            on_apply=self.apply_settings,
            on_reset_totals=self.sampler.reset_totals,
            icon_photo=self._tk_icon,
        )
        self._options_dialog.show()

    def open_connection_details(self, *_args) -> None:
        self.root.after(0, self._open_connection_details_ui)

    def _open_connection_details_ui(self) -> None:
        if self._details_dialog and self._details_dialog.win.winfo_exists():
            self._details_dialog.show()
            return
        self._details_dialog = ConnectionDetailsDialog(
            parent=self.root,
            current_adapter=self.settings.adapter,
            icon_photo=self._tk_icon,
        )
        self._details_dialog.show()

    def open_traffic_history(self, *_args) -> None:
        self.root.after(0, self._open_traffic_history_ui)

    def _open_traffic_history_ui(self) -> None:
        if self._history_dialog and self._history_dialog.win.winfo_exists():
            self._history_dialog.show()
            return
        self._history_dialog = TrafficHistoryDialog(
            parent=self.root,
            history=self.history_repository,
            icon_photo=self._tk_icon,
        )
        self._history_dialog.show()

    def exit(self, *_args) -> None:
        if self.settings.track_history:
            self.history_repository.save()
        self.settings_repository.save(self.settings)
        self.power_metrics.close()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.after(0, self.root.destroy)

    def run(self) -> None:
        self.root.mainloop()
