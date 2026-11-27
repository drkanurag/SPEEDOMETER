"""Floating Main Window and Windows Taskbar Window overlays (TrafficMonitor-style)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from speedometer_app.models import (
    NetworkSnapshot,
    Settings,
    SystemSnapshot,
    format_rate,
    format_total,
)
from speedometer_app.services import WindowsPlatformService
from speedometer_app.ui_widgets import SparklineCanvas, UsageBar


class MainOverlayWindow:
    """Skinnable, draggable floating desktop monitor with taskbar-size strip mode."""

    def __init__(
        self,
        root: tk.Tk,
        settings: Settings,
        on_context_menu: Callable[[tk.Event], None],
        on_open_options: Callable[[], None],
        on_position_changed: Callable[[int, int], None],
    ) -> None:
        self.root = root
        self.settings = settings
        self.on_context_menu = on_context_menu
        self.on_open_options = on_open_options
        self.on_position_changed = on_position_changed
        self._drag_origin: tuple[int, int] | None = None
        self._fullscreen_hidden = False
        self._last_network: NetworkSnapshot | None = None
        self._last_system: SystemSnapshot | None = None

        self.root.overrideredirect(True)
        self.root.bind("<Button-1>", self._begin_drag)
        self.root.bind("<B1-Motion>", self._drag)
        self.root.bind("<ButtonRelease-1>", self._end_drag)
        self.root.bind("<Double-Button-1>", lambda _e: self.on_open_options())
        self.root.bind("<Button-3>", self.on_context_menu)

        self.sparkline: SparklineCanvas | None = None
        self.cpu_bar: UsageBar | None = None
        self.ram_bar: UsageBar | None = None
        self._labels: dict[str, tk.Label] = {}
        self.rebuild()
        self.apply_position()

    def _bind_interactive(self, widget: tk.Widget) -> None:
        widget.bind("<Button-1>", self._begin_drag)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._end_drag)
        widget.bind("<Double-Button-1>", lambda _e: self.on_open_options())
        widget.bind("<Button-3>", self.on_context_menu)

    @staticmethod
    def _taskbar_height() -> int:
        tb = WindowsPlatformService.taskbar_rect()
        if tb:
            return max(36, tb[3] - tb[1])
        return 44

    def _is_taskbar_sized(self) -> bool:
        skin = "Compact Pill" if self.settings.compact else self.settings.skin
        return skin in ("Taskbar Strip", "Compact Pill")

    def rebuild(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self._labels.clear()
        self.sparkline = None
        self.cpu_bar = None
        self.ram_bar = None

        s = self.settings
        self.root.configure(bg=s.border)
        self.root.attributes("-alpha", s.opacity)
        self.root.attributes("-topmost", s.always_on_top)

        outer = tk.Frame(self.root, bg=s.border, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        self._bind_interactive(outer)

        skin = "Compact Pill" if s.compact else s.skin
        zero_rate = format_rate(0.0, s.unit_mode, s.precision)

        if skin == "Taskbar Strip":
            # Exact Windows taskbar-height two-row TrafficMonitor strip
            tb_h = self._taskbar_height()
            strip_font_size = min(s.font_size, 8) if tb_h <= 64 else min(s.font_size, 9)
            font_bold = (s.font, strip_font_size, "bold")
            font_reg = (s.font, strip_font_size)

            card = tk.Frame(outer, bg=s.background, padx=7, pady=1)
            card.pack(fill="both", expand=True)
            self._bind_interactive(card)

            if s.show_upload:
                ul = tk.Label(
                    card,
                    text=f"{s.label_upload} {zero_rate}",
                    font=font_bold,
                    bg=s.background,
                    fg=s.upload,
                    anchor="w",
                    width=10,
                )
                ul.grid(row=0, column=0, sticky="w")
                self._bind_interactive(ul)
                self._labels["up"] = ul

            if s.show_download:
                dl = tk.Label(
                    card,
                    text=f"{s.label_download} {zero_rate}",
                    font=font_bold,
                    bg=s.background,
                    fg=s.download,
                    anchor="w",
                    width=10,
                )
                dl.grid(row=1 if s.show_upload else 0, column=0, sticky="w")
                self._bind_interactive(dl)
                self._labels["down"] = dl

            if s.show_system_stats:
                cpu_lbl = tk.Label(
                    card,
                    text=f"{s.label_cpu} 0%",
                    font=font_reg,
                    bg=s.background,
                    fg=s.cpu,
                    anchor="w",
                    width=7,
                )
                cpu_lbl.grid(row=0, column=1, sticky="w", padx=(6, 0))
                self._bind_interactive(cpu_lbl)
                self._labels["cpu"] = cpu_lbl

                ram_lbl = tk.Label(
                    card,
                    text=f"{s.label_ram} 0%",
                    font=font_reg,
                    bg=s.background,
                    fg=s.ram,
                    anchor="w",
                    width=7,
                )
                ram_lbl.grid(row=1, column=1, sticky="w", padx=(6, 0))
                self._bind_interactive(ram_lbl)
                self._labels["ram"] = ram_lbl
        elif skin == "Compact Pill":
            pad_x, pad_y = 10, 5
            card = tk.Frame(outer, bg=s.background, padx=pad_x, pady=pad_y)
            card.pack(fill="both", expand=True)
            self._bind_interactive(card)

            font_main = (s.font, min(s.font_size, 10), "bold")
            speed_row = tk.Frame(card, bg=s.background)
            speed_row.pack(fill="both", expand=True)
            self._bind_interactive(speed_row)
            if s.show_download:
                dl = tk.Label(
                    speed_row,
                    text=f"{s.label_download} {zero_rate}",
                    font=font_main,
                    bg=s.background,
                    fg=s.download,
                    anchor="w",
                )
                dl.pack(side="left", padx=(0, 10 if s.show_upload else 0))
                self._bind_interactive(dl)
                self._labels["down"] = dl
            if s.show_upload:
                ul = tk.Label(
                    speed_row,
                    text=f"{s.label_upload} {zero_rate}",
                    font=font_main,
                    bg=s.background,
                    fg=s.upload,
                    anchor="w",
                )
                ul.pack(side="left")
                self._bind_interactive(ul)
                self._labels["up"] = ul
        else:
            card = tk.Frame(outer, bg=s.background, padx=13, pady=9)
            card.pack(fill="both", expand=True)
            self._bind_interactive(card)

            font_main = (s.font, s.font_size, "bold")
            font_sub = (s.font, max(8, s.font_size - 2))
            font_micro = (s.font, max(7, s.font_size - 3))
            row_idx = 0

            if s.show_adapter_name:
                hdr = tk.Frame(card, bg=s.background)
                hdr.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 5))
                self._bind_interactive(hdr)

                dot = tk.Label(hdr, text="●", font=font_micro, bg=s.background, fg=s.download)
                dot.pack(side="left", padx=(0, 4))
                self._bind_interactive(dot)

                adapter_lbl = tk.Label(
                    hdr,
                    text="All active",
                    font=(s.font, max(7, s.font_size - 3), "bold"),
                    bg=s.background,
                    fg=s.muted,
                    anchor="w",
                )
                adapter_lbl.pack(side="left", fill="x", expand=True)
                self._bind_interactive(adapter_lbl)
                self._labels["adapter"] = adapter_lbl

                if skin == "Detailed Dashboard":
                    badge = tk.Label(
                        hdr,
                        text="LIVE",
                        font=(s.font, max(7, s.font_size - 4), "bold"),
                        bg=s.surface,
                        fg=s.download,
                        padx=5,
                        pady=1,
                    )
                    badge.pack(side="right")
                    self._bind_interactive(badge)
                row_idx += 1

            card.grid_columnconfigure(0, minsize=95)
            card.grid_columnconfigure(1, minsize=105)
            if s.show_download:
                dl_tag = tk.Label(
                    card,
                    text=f"{s.label_download}  Download",
                    font=font_sub,
                    bg=s.background,
                    fg=s.muted,
                    anchor="w",
                )
                dl_tag.grid(row=row_idx, column=0, sticky="w", pady=(0, 2))
                self._bind_interactive(dl_tag)

                dl_val = tk.Label(card, text=zero_rate, font=font_main, bg=s.background, fg=s.download, anchor="e")
                dl_val.grid(row=row_idx, column=1, sticky="e", pady=(0, 2))
                self._bind_interactive(dl_val)
                self._labels["down"] = dl_val
                row_idx += 1

            if s.show_upload:
                ul_tag = tk.Label(
                    card,
                    text=f"{s.label_upload}  Upload",
                    font=font_sub,
                    bg=s.background,
                    fg=s.muted,
                    anchor="w",
                )
                ul_tag.grid(row=row_idx, column=0, sticky="w", pady=(0, 2))
                self._bind_interactive(ul_tag)

                ul_val = tk.Label(card, text=zero_rate, font=font_main, bg=s.background, fg=s.upload, anchor="e")
                ul_val.grid(row=row_idx, column=1, sticky="e", pady=(0, 2))
                self._bind_interactive(ul_val)
                self._labels["up"] = ul_val
                row_idx += 1

            if s.show_sparkline:
                spark_wrap = tk.Frame(card, bg=s.surface, padx=4, pady=3)
                spark_wrap.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(5, 2))
                self._bind_interactive(spark_wrap)
                self.sparkline = SparklineCanvas(
                    spark_wrap,
                    width=200,
                    height=30 if skin == "Detailed Dashboard" else 24,
                    bg=s.surface,
                    down_color=s.download,
                    up_color=s.upload,
                    grid_color=s.border,
                )
                self.sparkline.pack(fill="x", expand=True)
                self._bind_interactive(self.sparkline)
                row_idx += 1

            if s.show_system_stats:
                if skin == "Detailed Dashboard":
                    sys_frame = tk.Frame(card, bg=s.background)
                    sys_frame.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(5, 0))
                    sys_frame.grid_columnconfigure(1, weight=1)
                    self._bind_interactive(sys_frame)

                    cpu_lbl = tk.Label(
                        sys_frame,
                        text=f"{s.label_cpu} 0%",
                        font=font_micro,
                        bg=s.background,
                        fg=s.foreground,
                        anchor="w",
                        width=9,
                    )
                    cpu_lbl.grid(row=0, column=0, sticky="w")
                    self._bind_interactive(cpu_lbl)
                    self._labels["cpu"] = cpu_lbl

                    self.cpu_bar = UsageBar(
                        sys_frame, width=110, height=5, track_color=s.surface, fill_color=s.cpu, bg=s.background
                    )
                    self.cpu_bar.grid(row=0, column=1, sticky="e", padx=(6, 0))
                    self._bind_interactive(self.cpu_bar)

                    ram_lbl = tk.Label(
                        sys_frame,
                        text=f"{s.label_ram} 0%",
                        font=font_micro,
                        bg=s.background,
                        fg=s.foreground,
                        anchor="w",
                        width=9,
                    )
                    ram_lbl.grid(row=1, column=0, sticky="w", pady=(3, 0))
                    self._bind_interactive(ram_lbl)
                    self._labels["ram"] = ram_lbl

                    self.ram_bar = UsageBar(
                        sys_frame, width=110, height=5, track_color=s.surface, fill_color=s.ram, bg=s.background
                    )
                    self.ram_bar.grid(row=1, column=1, sticky="e", padx=(6, 0), pady=(3, 0))
                    self._bind_interactive(self.ram_bar)
                else:
                    sys_lbl = tk.Label(
                        card,
                        text=f"{s.label_cpu} 0%   •   {s.label_ram} 0%",
                        font=font_micro,
                        bg=s.background,
                        fg=s.muted,
                        anchor="w",
                    )
                    sys_lbl.grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(4, 0))
                    self._bind_interactive(sys_lbl)
                    self._labels["sys"] = sys_lbl
                row_idx += 1

            if s.show_totals:
                totals_lbl = tk.Label(
                    card,
                    text="Session  ↓ 0 B   ↑ 0 B",
                    font=font_micro,
                    bg=s.background,
                    fg=s.muted,
                    anchor="w",
                )
                totals_lbl.grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(3, 0))
                self._bind_interactive(totals_lbl)
                self._labels["totals"] = totals_lbl

        self.root.update_idletasks()
        WindowsPlatformService.apply_rounded_corners(self.root, small=self._is_taskbar_sized(), border_hex=s.border)
        WindowsPlatformService.set_tool_window(self.root)
        WindowsPlatformService.set_mouse_penetrate(self.root, s.mouse_penetrate)
        if self._last_network is not None and self._last_system is not None:
            self.update_data(self._last_network, self._last_system)
        self.apply_visibility()

    def update_data(self, network: NetworkSnapshot, system: SystemSnapshot) -> None:
        self._last_network = network
        self._last_system = system
        s = self.settings
        down_str = format_rate(network.download_bytes_per_second, s.unit_mode, s.precision)
        up_str = format_rate(network.upload_bytes_per_second, s.unit_mode, s.precision)

        if "adapter" in self._labels:
            label = network.active_adapter_label
            if len(label) > 22:
                label = label[:20] + "…"
            self._labels["adapter"].configure(text=label)

        inline_prefix = self._is_taskbar_sized()
        if "down" in self._labels:
            text = f"{s.label_download} {down_str}" if inline_prefix else down_str
            self._labels["down"].configure(text=text)

        if "up" in self._labels:
            text = f"{s.label_upload} {up_str}" if inline_prefix else up_str
            self._labels["up"].configure(text=text)

        if self.sparkline is not None:
            self.sparkline.push(network.download_bytes_per_second, network.upload_bytes_per_second)

        if "sys" in self._labels:
            self._labels["sys"].configure(
                text=f"{s.label_cpu} {system.cpu_percent:.0f}%   •   {s.label_ram} {system.memory_percent:.0f}%"
            )
        if "cpu" in self._labels:
            self._labels["cpu"].configure(text=f"{s.label_cpu} {system.cpu_percent:.0f}%")
        if self.cpu_bar is not None:
            self.cpu_bar.set_percent(system.cpu_percent)
        if "ram" in self._labels:
            self._labels["ram"].configure(text=f"{s.label_ram} {system.memory_percent:.0f}%")
        if self.ram_bar is not None:
            self.ram_bar.set_percent(system.memory_percent)

        if "totals" in self._labels:
            self._labels["totals"].configure(
                text=f"Session  ↓ {format_total(network.session_download_bytes)}   ↑ {format_total(network.session_upload_bytes)}"
            )

    def apply_position(self) -> None:
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        s = self.settings
        taskbar = WindowsPlatformService.taskbar_rect()

        if s.dock_to_taskbar and taskbar:
            tb_left, tb_top, tb_right, tb_bottom = taskbar
            tb_h = max(tb_bottom - tb_top, h)
            if self._is_taskbar_sized():
                h = min(h, max(tb_h - 4, 34))
                y = tb_top + max((tb_h - h) // 2, 0)
                if s.dock_side == "Left":
                    x = tb_left + max(8, s.taskbar_offset_x)
                else:
                    notify = WindowsPlatformService.tray_notify_rect()
                    anchor_right = notify[0] if notify else (tb_right - 190)
                    x = max(tb_left + 8, anchor_right - w - max(6, s.taskbar_offset_x))
            else:
                x = (tb_right - w - 10) if s.dock_side == "Right" else (tb_left + 10)
                y = max(0, tb_top - h - 6)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            return

        wa_left, wa_top, wa_right, wa_bottom = WindowsPlatformService.work_area()
        if s.window_x is not None and s.window_y is not None:
            x = max(wa_left, min(s.window_x, wa_right - w))
            y = max(wa_top, min(s.window_y, wa_bottom - h))
        else:
            x = wa_right - w - 16
            y = wa_bottom - h - 16
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def apply_visibility(self) -> None:
        if self.settings.show_main_window and not self._fullscreen_hidden:
            self.root.deiconify()
            if self.settings.always_on_top:
                self.root.attributes("-topmost", True)
                WindowsPlatformService.keep_topmost(self.root)
        else:
            self.root.withdraw()

    def ensure_topmost(self) -> None:
        if self.settings.show_main_window and self.settings.always_on_top and not self._fullscreen_hidden:
            WindowsPlatformService.keep_topmost(self.root)

    def set_fullscreen_hidden(self, hidden: bool) -> None:
        if self._fullscreen_hidden != hidden:
            self._fullscreen_hidden = hidden
            self.apply_visibility()

    def _begin_drag(self, event: tk.Event) -> None:
        if self.settings.lock_position or self.settings.mouse_penetrate:
            return
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        if not self._drag_origin or self.settings.lock_position:
            return
        x = event.x_root - self._drag_origin[0]
        y = event.y_root - self._drag_origin[1]
        wa_left, wa_top, wa_right, wa_bottom = WindowsPlatformService.work_area()
        w, h = self.root.winfo_width(), self.root.winfo_height()

        if abs(x - wa_left) <= 10:
            x = wa_left
        elif abs((x + w) - wa_right) <= 10:
            x = wa_right - w
        if abs(y - wa_top) <= 10:
            y = wa_top
        elif abs((y + h) - wa_bottom) <= 10:
            y = wa_bottom - h

        # Magnetic vertical align into the Windows taskbar when dragging a taskbar-sized skin
        taskbar = WindowsPlatformService.taskbar_rect()
        if taskbar and self._is_taskbar_sized():
            tb_top, tb_bottom = taskbar[1], taskbar[3]
            tb_center_y = tb_top + max(((tb_bottom - tb_top) - h) // 2, 0)
            if y >= tb_top - 14:
                y = tb_center_y

        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, _event: tk.Event) -> None:
        if self._drag_origin is not None:
            self._drag_origin = None
            if not self.settings.lock_position:
                self.on_position_changed(self.root.winfo_x(), self.root.winfo_y())


class TaskbarOverlayWindow:
    """TrafficMonitor-style compact monitor aligned inside the Windows taskbar band."""

    def __init__(
        self,
        root: tk.Tk,
        settings: Settings,
        on_context_menu: Callable[[tk.Event], None],
        on_open_options: Callable[[], None],
    ) -> None:
        self.parent_root = root
        self.settings = settings
        self.on_context_menu = on_context_menu
        self.on_open_options = on_open_options
        self._fullscreen_hidden = False
        self._last_network: NetworkSnapshot | None = None
        self._last_system: SystemSnapshot | None = None
        self._drag_origin: tuple[int, int] | None = None

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.bind("<Button-3>", self.on_context_menu)
        self.win.bind("<Double-Button-1>", lambda _e: self.on_open_options())

        self._labels: dict[str, tk.Label] = {}
        self.rebuild()

    def _resolved_colors(self) -> tuple[str, str, str, str, str]:
        s = self.settings
        if s.taskbar_auto_theme:
            if WindowsPlatformService.is_system_light_theme():
                return ("#EFF3F8", "#D4DCE8", "#182233", "#087F5B", "#1D63DC")
            return ("#1F1F1F", "#343434", "#F4F6FA", "#6CCB5F", "#60CDFF")
        return (
            s.taskbar_background,
            s.border,
            s.taskbar_foreground,
            s.taskbar_download,
            s.taskbar_upload,
        )

    def _bind_events(self, widget: tk.Widget) -> None:
        widget.bind("<Button-1>", self._begin_drag)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._end_drag)
        widget.bind("<Button-3>", self.on_context_menu)
        widget.bind("<Double-Button-1>", lambda _e: self.on_open_options())

    def _begin_drag(self, event: tk.Event) -> None:
        if self.settings.lock_position:
            return
        self._drag_origin = (event.x_root - self.win.winfo_x(), self.win.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        if not self._drag_origin or self.settings.lock_position:
            return
        x = event.x_root - self._drag_origin[0]
        y = self._drag_origin[1]
        self.win.geometry(f"+{x}+{y}")

    def _end_drag(self, _event: tk.Event) -> None:
        self._drag_origin = None

    def rebuild(self) -> None:
        for child in self.win.winfo_children():
            child.destroy()
        self._labels.clear()

        s = self.settings
        bg, border, fg, dl_col, ul_col = self._resolved_colors()
        self.win.configure(bg=bg)

        frame = tk.Frame(self.win, bg=bg, highlightbackground=border, highlightthickness=1, padx=8, pady=2)
        frame.pack(fill="both", expand=True)
        self._bind_events(frame)

        font_reg = (s.font, s.taskbar_font_size)
        font_bold = (s.font, s.taskbar_font_size, "bold")
        zero_rate = format_rate(0.0, s.unit_mode, s.precision)

        if s.taskbar_layout == "Horizontal":
            col = 0
            specs = [
                ("down", s.taskbar_show_download, f"{s.label_download} {zero_rate}", dl_col, font_bold, 10),
                ("up", s.taskbar_show_upload, f"{s.label_upload} {zero_rate}", ul_col, font_bold, 10),
                ("cpu", s.taskbar_show_cpu, f"{s.label_cpu} 0%", fg, font_reg, 7),
                ("ram", s.taskbar_show_ram, f"{s.label_ram} 0%", fg, font_reg, 7),
            ]
            for key, visible, init_text, color, font, min_w in specs:
                if not visible:
                    continue
                lbl = tk.Label(frame, text=init_text, font=font, bg=bg, fg=color, anchor="w", width=min_w)
                lbl.grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 8, 0))
                self._bind_events(lbl)
                self._labels[key] = lbl
                col += 1
        else:
            if s.taskbar_show_upload:
                ul = tk.Label(
                    frame, text=f"{s.label_upload} {zero_rate}", font=font_bold, bg=bg, fg=ul_col, anchor="w", width=11
                )
                ul.grid(row=0, column=0, sticky="w")
                self._bind_events(ul)
                self._labels["up"] = ul
            if s.taskbar_show_download:
                dl = tk.Label(
                    frame, text=f"{s.label_download} {zero_rate}", font=font_bold, bg=bg, fg=dl_col, anchor="w", width=11
                )
                dl.grid(row=1, column=0, sticky="w")
                self._bind_events(dl)
                self._labels["down"] = dl
            if s.taskbar_show_cpu:
                cpu = tk.Label(frame, text=f"{s.label_cpu} 0%", font=font_reg, bg=bg, fg=fg, anchor="w", width=8)
                cpu.grid(row=0, column=1, sticky="w", padx=(8, 0))
                self._bind_events(cpu)
                self._labels["cpu"] = cpu
            if s.taskbar_show_ram:
                ram = tk.Label(frame, text=f"{s.label_ram} 0%", font=font_reg, bg=bg, fg=fg, anchor="w", width=8)
                ram.grid(row=1, column=1, sticky="w", padx=(8, 0))
                self._bind_events(ram)
                self._labels["ram"] = ram

        self.apply_position()
        WindowsPlatformService.apply_rounded_corners(self.win, small=True, border_hex=border)
        WindowsPlatformService.set_tool_window(self.win)
        if self._last_network is not None and self._last_system is not None:
            self.update_data(self._last_network, self._last_system)
        self.apply_visibility()

    def apply_position(self) -> None:
        self.win.update_idletasks()
        w = max(self.win.winfo_reqwidth(), 80)
        h = max(self.win.winfo_reqheight(), 28)

        taskbar = WindowsPlatformService.taskbar_rect()
        s = self.settings
        if taskbar:
            tb_left, tb_top, tb_right, tb_bottom = taskbar
            tb_h = max(tb_bottom - tb_top, h)
            h = min(h, max(tb_h - 4, 28)) if s.taskbar_layout == "Two-Row" else min(h, tb_h - 8)
            y = tb_top + max((tb_h - h) // 2, 0)
            if s.taskbar_side == "Left":
                x = tb_left + max(0, s.taskbar_offset_x)
            else:
                notify = WindowsPlatformService.tray_notify_rect()
                anchor_right = notify[0] if notify else (tb_right - 190)
                x = max(tb_left + 8, anchor_right - w - max(0, s.taskbar_offset_x))
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            return

        wa_left, _wa_top, wa_right, wa_bottom = WindowsPlatformService.work_area()
        x = (wa_left + 12) if s.taskbar_side == "Left" else (wa_right - w - 12)
        y = wa_bottom - h - 8
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def update_data(self, network: NetworkSnapshot, system: SystemSnapshot) -> None:
        self._last_network = network
        self._last_system = system
        s = self.settings
        if "down" in self._labels:
            self._labels["down"].configure(
                text=f"{s.label_download} {format_rate(network.download_bytes_per_second, s.unit_mode, s.precision)}"
            )
        if "up" in self._labels:
            self._labels["up"].configure(
                text=f"{s.label_upload} {format_rate(network.upload_bytes_per_second, s.unit_mode, s.precision)}"
            )
        if "cpu" in self._labels:
            self._labels["cpu"].configure(text=f"{s.label_cpu} {system.cpu_percent:.0f}%")
        if "ram" in self._labels:
            self._labels["ram"].configure(text=f"{s.label_ram} {system.memory_percent:.0f}%")

    def apply_visibility(self) -> None:
        if self.settings.show_taskbar_window and not self._fullscreen_hidden:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            WindowsPlatformService.keep_topmost(self.win)
        else:
            self.win.withdraw()

    def set_fullscreen_hidden(self, hidden: bool) -> None:
        if self._fullscreen_hidden != hidden:
            self._fullscreen_hidden = hidden
            self.apply_visibility()

    def ensure_topmost(self) -> None:
        if self.settings.show_taskbar_window and not self._fullscreen_hidden:
            WindowsPlatformService.keep_topmost(self.win)
