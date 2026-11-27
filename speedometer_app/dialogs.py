"""TrafficMonitor-inspired Options, Connection Details, and Historical Traffic dialogs."""

from __future__ import annotations

import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Callable

from speedometer_app.models import (
    APP_NAME,
    APP_VERSION,
    CONFIG_DIR,
    FONTS,
    SKINS,
    THEMES,
    UNIT_MODES,
    AdapterInfo,
    Settings,
    format_rate,
    format_total,
)
from speedometer_app.services import (
    NetworkSampler,
    SettingsRepository,
    TrafficHistoryRepository,
    WindowsPlatformService,
)


def _make_dialog(parent: tk.Tk, title: str, width: int, height: int, icon_photo=None) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(f"{width}x{height}")
    win.minsize(width - 40, height - 40)
    win.configure(bg="#F5F7FB")
    if icon_photo is not None:
        try:
            win.iconphoto(False, icon_photo)
        except tk.TclError:
            pass
    win.update_idletasks()
    # Center on screen
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(20, (sw - width) // 2)
    y = max(20, (sh - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")
    return win


class OptionsDialog:
    """Tabbed TrafficMonitor-style configuration dialog with live Apply."""

    def __init__(
        self,
        parent: tk.Tk,
        settings: Settings,
        sampler: NetworkSampler,
        on_apply: Callable[[Settings], None],
        on_reset_totals: Callable[[], None],
        icon_photo=None,
    ) -> None:
        self.parent = parent
        self.sampler = sampler
        self.on_apply = on_apply
        self.on_reset_totals = on_reset_totals
        self._working = Settings(**asdict(settings))

        self.win = _make_dialog(parent, f"{APP_NAME} Options", 700, 660, icon_photo)
        self.win.resizable(True, True)
        self._vars: dict[str, tk.Variable] = {}
        self._color_buttons: dict[str, tk.Button] = {}
        self._build()
        self.win.update_idletasks()
        req_w = max(700, self.win.winfo_reqwidth() + 16)
        req_h = max(660, self.win.winfo_reqheight() + 16)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        final_w = min(req_w, sw - 40)
        final_h = min(req_h, sh - 60)
        x = max(20, (sw - final_w) // 2)
        y = max(20, (sh - final_h) // 2)
        self.win.geometry(f"{final_w}x{final_h}+{x}+{y}")
        self.win.minsize(min(680, final_w), min(620, final_h))

    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        wrap = tk.Frame(parent, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=14, pady=10)
        wrap.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(wrap, text=title, bg="#FFFFFF", fg="#162032", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        return wrap

    def _build(self) -> None:
        s = self._working

        # Header banner
        hdr = tk.Frame(self.win, bg="#162032", padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"{APP_NAME} Options", bg="#162032", fg="#FFFFFF", font=("Segoe UI", 13, "bold")).pack(
            side="left"
        )
        tk.Label(
            hdr,
            text=f"v{APP_VERSION}  •  Traffic & System Monitor",
            bg="#162032",
            fg="#9DB1CE",
            font=("Segoe UI", 9),
        ).pack(side="right")

        notebook = ttk.Notebook(self.win)
        notebook.pack(fill="both", expand=True, padx=12, pady=(10, 6))

        tab_general = ttk.Frame(notebook)
        tab_main = ttk.Frame(notebook)
        tab_taskbar = ttk.Frame(notebook)
        tab_advanced = ttk.Frame(notebook)
        notebook.add(tab_general, text="  General  ")
        notebook.add(tab_main, text="  Main Window  ")
        notebook.add(tab_taskbar, text="  Taskbar Window  ")
        notebook.add(tab_advanced, text="  Display & Data  ")

        self._vars = {
            "adapter": tk.StringVar(value=s.adapter),
            "show_virtual_adapters": tk.BooleanVar(value=s.show_virtual_adapters),
            "interval": tk.StringVar(value=str(s.interval)),
            "unit_mode": tk.StringVar(value=s.unit_mode),
            "precision": tk.IntVar(value=s.precision),
            "start_with_windows": tk.BooleanVar(value=s.start_with_windows),
            "auto_hide_fullscreen": tk.BooleanVar(value=s.auto_hide_fullscreen),
            "track_history": tk.BooleanVar(value=s.track_history),
            # Main window
            "show_main_window": tk.BooleanVar(value=s.show_main_window),
            "skin": tk.StringVar(value=s.skin),
            "compact": tk.BooleanVar(value=s.compact),
            "font": tk.StringVar(value=s.font),
            "font_size": tk.StringVar(value=str(s.font_size)),
            "opacity": tk.DoubleVar(value=round(s.opacity * 100)),
            "show_download": tk.BooleanVar(value=s.show_download),
            "show_upload": tk.BooleanVar(value=s.show_upload),
            "show_totals": tk.BooleanVar(value=s.show_totals),
            "show_system_stats": tk.BooleanVar(value=s.show_system_stats),
            "show_power_watts": tk.BooleanVar(value=s.show_power_watts),
            "show_sparkline": tk.BooleanVar(value=s.show_sparkline),
            "show_adapter_name": tk.BooleanVar(value=s.show_adapter_name),
            "always_on_top": tk.BooleanVar(value=s.always_on_top),
            "lock_position": tk.BooleanVar(value=s.lock_position),
            "mouse_penetrate": tk.BooleanVar(value=s.mouse_penetrate),
            "dock_to_taskbar": tk.BooleanVar(value=s.dock_to_taskbar),
            "dock_side": tk.StringVar(value=s.dock_side),
            # Taskbar window
            "show_taskbar_window": tk.BooleanVar(value=s.show_taskbar_window),
            "taskbar_side": tk.StringVar(value=s.taskbar_side),
            "taskbar_offset_x": tk.IntVar(value=s.taskbar_offset_x),
            "taskbar_layout": tk.StringVar(value=s.taskbar_layout),
            "taskbar_auto_theme": tk.BooleanVar(value=s.taskbar_auto_theme),
            "taskbar_font_size": tk.StringVar(value=str(s.taskbar_font_size)),
            "taskbar_show_download": tk.BooleanVar(value=s.taskbar_show_download),
            "taskbar_show_upload": tk.BooleanVar(value=s.taskbar_show_upload),
            "taskbar_show_cpu": tk.BooleanVar(value=s.taskbar_show_cpu),
            "taskbar_show_ram": tk.BooleanVar(value=s.taskbar_show_ram),
            "taskbar_show_power_watts": tk.BooleanVar(value=s.taskbar_show_power_watts),
            # Labels
            "label_download": tk.StringVar(value=s.label_download),
            "label_upload": tk.StringVar(value=s.label_upload),
            "label_cpu": tk.StringVar(value=s.label_cpu),
            "label_ram": tk.StringVar(value=s.label_ram),
            "label_power": tk.StringVar(value=s.label_power),
        }

        self._build_general_tab(tab_general)
        self._build_main_tab(tab_main)
        self._build_taskbar_tab(tab_taskbar)
        self._build_advanced_tab(tab_advanced)

        # Bottom action bar
        footer = tk.Frame(self.win, bg="#F5F7FB", padx=14, pady=10)
        footer.pack(fill="x")
        ttk.Button(footer, text="Reset Defaults", command=self._reset_defaults).pack(side="left")
        self._save_status = tk.Label(footer, text="", bg="#F5F7FB", fg="#087F5B", font=("Segoe UI", 9, "bold"))
        self._save_status.pack(side="left", padx=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save Changes", command=self._apply_only).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save & Close", style="Accent.TButton", command=self._ok).pack(side="right")

    def _build_general_tab(self, tab: ttk.Frame) -> None:
        c1 = self._card(tab, "Network Monitoring")
        grid = tk.Frame(c1, bg="#FFFFFF")
        grid.pack(fill="x")
        grid.grid_columnconfigure(1, weight=1)

        choices = [NetworkSampler.AUTO_ALL, NetworkSampler.AUTO_PRIMARY] + self.sampler.adapters(
            include_virtual=bool(self._vars["show_virtual_adapters"].get())
        )
        if self._vars["adapter"].get() not in choices:
            choices.append(self._vars["adapter"].get())

        tk.Label(grid, text="Network adapter", bg="#FFFFFF", fg="#162032").grid(row=0, column=0, sticky="w", pady=4)
        self._adapter_combo = ttk.Combobox(
            grid, values=choices, textvariable=self._vars["adapter"], state="readonly", width=34
        )
        self._adapter_combo.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)

        def refresh_adapters() -> None:
            inc = bool(self._vars["show_virtual_adapters"].get())
            vals = [NetworkSampler.AUTO_ALL, NetworkSampler.AUTO_PRIMARY] + self.sampler.adapters(include_virtual=inc)
            if self._vars["adapter"].get() not in vals:
                vals.append(self._vars["adapter"].get())
            self._adapter_combo.configure(values=vals)

        ttk.Checkbutton(
            c1,
            text="Include virtual adapters (Hyper-V, WSL, Docker, VMware)",
            variable=self._vars["show_virtual_adapters"],
            command=refresh_adapters,
        ).pack(anchor="w", pady=(4, 2))

        c2 = self._card(tab, "Units & Sampling")
        g2 = tk.Frame(c2, bg="#FFFFFF")
        g2.pack(fill="x")
        g2.grid_columnconfigure(1, weight=1)

        tk.Label(g2, text="Refresh interval (sec)", bg="#FFFFFF", fg="#162032").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            g2, values=("0.25", "0.5", "1.0", "2.0", "3.0"), textvariable=self._vars["interval"], state="readonly", width=12
        ).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=4)

        tk.Label(g2, text="Speed units", bg="#FFFFFF", fg="#162032").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            g2, values=UNIT_MODES, textvariable=self._vars["unit_mode"], state="readonly", width=20
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=4)

        tk.Label(g2, text="Decimal precision", bg="#FFFFFF", fg="#162032").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(
            g2, values=(0, 1, 2), textvariable=self._vars["precision"], state="readonly", width=8
        ).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=4)

        c3 = self._card(tab, "Behavior & Startup")
        ttk.Checkbutton(c3, text="Start Speedometer automatically with Windows", variable=self._vars["start_with_windows"]).pack(
            anchor="w", pady=2
        )
        ttk.Checkbutton(
            c3,
            text="Auto-hide monitor overlays when a fullscreen app or game is active",
            variable=self._vars["auto_hide_fullscreen"],
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            c3,
            text="Record daily historical traffic usage",
            variable=self._vars["track_history"],
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            c3,
            text="Show real-time laptop power consumption (Watts only, W)",
            variable=self._vars["show_power_watts"],
        ).pack(anchor="w", pady=2)

    def _build_main_tab(self, tab: ttk.Frame) -> None:
        c1 = self._card(tab, "Layout & Skin")
        ttk.Checkbutton(c1, text="Show Floating Main Window", variable=self._vars["show_main_window"]).pack(anchor="w", pady=(0, 6))

        g = tk.Frame(c1, bg="#FFFFFF")
        g.pack(fill="x")
        tk.Label(g, text="Skin preset", bg="#FFFFFF", fg="#162032").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(g, values=SKINS, textvariable=self._vars["skin"], state="readonly", width=22).grid(
            row=0, column=1, sticky="w", padx=(10, 16), pady=3
        )
        tk.Label(g, text="Font", bg="#FFFFFF", fg="#162032").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(g, values=FONTS, textvariable=self._vars["font"], state="readonly", width=18).grid(
            row=1, column=1, sticky="w", padx=(10, 16), pady=3
        )
        tk.Label(g, text="Size", bg="#FFFFFF", fg="#162032").grid(row=1, column=2, sticky="w", pady=3)
        ttk.Combobox(
            g, values=("9", "10", "11", "12", "13", "14", "16"), textvariable=self._vars["font_size"], state="readonly", width=6
        ).grid(row=1, column=3, sticky="w", padx=(6, 0), pady=3)

        op_row = tk.Frame(c1, bg="#FFFFFF")
        op_row.pack(fill="x", pady=(6, 0))
        tk.Label(op_row, text="Opacity (%)", bg="#FFFFFF", fg="#162032").pack(side="left")
        ttk.Scale(op_row, from_=35, to=100, variable=self._vars["opacity"], orient="horizontal", length=220).pack(
            side="left", padx=(12, 8)
        )
        self._op_label = tk.Label(op_row, text=f"{int(self._vars['opacity'].get())}%", bg="#FFFFFF", fg="#5A697E")
        self._op_label.pack(side="left")
        self._vars["opacity"].trace_add("write", lambda *_: self._update_opacity_lbl())

        c2 = self._card(tab, "Visible Items & Window Behavior")
        cols = tk.Frame(c2, bg="#FFFFFF")
        cols.pack(fill="x")
        left_col = tk.Frame(cols, bg="#FFFFFF")
        left_col.pack(side="left", fill="both", expand=True)
        right_col = tk.Frame(cols, bg="#FFFFFF")
        right_col.pack(side="left", fill="both", expand=True)

        for label, key in (
            ("Show Download speed", "show_download"),
            ("Show Upload speed", "show_upload"),
            ("Show Live Sparkline graph", "show_sparkline"),
            ("Show CPU & RAM usage", "show_system_stats"),
            ("Show Power consumption (W)", "show_power_watts"),
            ("Show Session totals", "show_totals"),
            ("Show Active adapter header", "show_adapter_name"),
        ):
            ttk.Checkbutton(left_col, text=label, variable=self._vars[key]).pack(anchor="w", pady=1)

        for label, key in (
            ("Always on top", "always_on_top"),
            ("Lock window position", "lock_position"),
            ("Mouse penetrate (click-through)", "mouse_penetrate"),
            ("Compact mode", "compact"),
            ("Align inside / at taskbar", "dock_to_taskbar"),
        ):
            ttk.Checkbutton(right_col, text=label, variable=self._vars[key]).pack(anchor="w", pady=1)

        dock_row = tk.Frame(right_col, bg="#FFFFFF")
        dock_row.pack(anchor="w", pady=(3, 0))
        tk.Label(dock_row, text="Taskbar side:", bg="#FFFFFF", fg="#162032").pack(side="left")
        ttk.Combobox(
            dock_row, values=("Right", "Left"), textvariable=self._vars["dock_side"], state="readonly", width=8
        ).pack(side="left", padx=(6, 0))

        c3 = self._card(tab, "Theme & Custom Colors")
        swatches = tk.Frame(c3, bg="#FFFFFF")
        swatches.pack(fill="x", pady=(0, 8))
        tk.Label(swatches, text="Themes:", bg="#FFFFFF", fg="#5A697E").pack(side="left", padx=(0, 6))
        for theme_name in THEMES:
            ttk.Button(
                swatches,
                text=theme_name,
                command=lambda n=theme_name: self._apply_theme_preset(n),
            ).pack(side="left", padx=2)

        colors_row = tk.Frame(c3, bg="#FFFFFF")
        colors_row.pack(fill="x")
        for label, key in (
            ("Background", "background"),
            ("Text", "foreground"),
            ("Download", "download"),
            ("Upload", "upload"),
            ("CPU", "cpu"),
            ("RAM", "ram"),
            ("Power", "power"),
        ):
            btn = tk.Button(
                colors_row,
                text=label,
                bg=getattr(self._working, key),
                fg=self._contrast_fg(getattr(self._working, key)),
                relief="flat",
                padx=8,
                pady=4,
                font=("Segoe UI", 8, "bold"),
                command=lambda k=key: self._pick_color(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._color_buttons[key] = btn

    def _build_taskbar_tab(self, tab: ttk.Frame) -> None:
        c1 = self._card(tab, "Windows Taskbar Monitor (TrafficMonitor Mode)")
        ttk.Checkbutton(
            c1,
            text="Show embedded monitor inside the Windows taskbar",
            variable=self._vars["show_taskbar_window"],
        ).pack(anchor="w", pady=(0, 6))

        g = tk.Frame(c1, bg="#FFFFFF")
        g.pack(fill="x")
        tk.Label(g, text="Taskbar layout", bg="#FFFFFF", fg="#162032").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            g, values=("Two-Row", "Horizontal"), textvariable=self._vars["taskbar_layout"], state="readonly", width=16
        ).grid(row=0, column=1, sticky="w", padx=(12, 20), pady=4)

        tk.Label(g, text="Font size", bg="#FFFFFF", fg="#162032").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Combobox(
            g, values=("8", "9", "10", "11"), textvariable=self._vars["taskbar_font_size"], state="readonly", width=6
        ).grid(row=0, column=3, sticky="w", padx=(8, 0), pady=4)

        tk.Label(g, text="Taskbar side", bg="#FFFFFF", fg="#162032").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            g, values=("Right", "Left"), textvariable=self._vars["taskbar_side"], state="readonly", width=16
        ).grid(row=1, column=1, sticky="w", padx=(12, 20), pady=4)

        tk.Label(g, text="Horizontal margin (px)", bg="#FFFFFF", fg="#162032").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Spinbox(g, from_=0, to=400, textvariable=self._vars["taskbar_offset_x"], width=7).grid(
            row=1, column=3, sticky="w", padx=(8, 0), pady=4
        )
        tk.Label(
            c1,
            text="Tip: Increase Horizontal margin (e.g. 140 px on Left) to avoid Windows 11 Widgets.",
            bg="#FFFFFF",
            fg="#5A697E",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(6, 0))

        c2 = self._card(tab, "Taskbar Visible Metrics & Theme")
        row = tk.Frame(c2, bg="#FFFFFF")
        row.pack(fill="x")
        for label, key in (
            ("Download", "taskbar_show_download"),
            ("Upload", "taskbar_show_upload"),
            ("CPU %", "taskbar_show_cpu"),
            ("RAM %", "taskbar_show_ram"),
            ("Power (W)", "taskbar_show_power_watts"),
        ):
            ttk.Checkbutton(row, text=label, variable=self._vars[key]).pack(side="left", padx=(0, 14))

        ttk.Checkbutton(
            c2,
            text="Automatically match Windows 11 Light/Dark taskbar theme",
            variable=self._vars["taskbar_auto_theme"],
        ).pack(anchor="w", pady=(8, 6))

        tb_colors = tk.Frame(c2, bg="#FFFFFF")
        tb_colors.pack(fill="x")
        for label, key in (
            ("TB Background", "taskbar_background"),
            ("TB Text", "taskbar_foreground"),
            ("TB Download", "taskbar_download"),
            ("TB Upload", "taskbar_upload"),
        ):
            btn = tk.Button(
                tb_colors,
                text=label,
                bg=getattr(self._working, key),
                fg=self._contrast_fg(getattr(self._working, key)),
                relief="flat",
                padx=8,
                pady=4,
                font=("Segoe UI", 8, "bold"),
                command=lambda k=key: self._pick_color(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._color_buttons[key] = btn

    def _build_advanced_tab(self, tab: ttk.Frame) -> None:
        c1 = self._card(tab, "Custom Metric Labels")
        g = tk.Frame(c1, bg="#FFFFFF")
        g.pack(fill="x")
        for idx, (label, key) in enumerate(
            (
                ("Download prefix", "label_download"),
                ("Upload prefix", "label_upload"),
                ("CPU prefix", "label_cpu"),
                ("RAM prefix", "label_ram"),
                ("Power prefix", "label_power"),
            )
        ):
            tk.Label(g, text=label, bg="#FFFFFF", fg="#162032").grid(row=idx // 2, column=(idx % 2) * 2, sticky="w", pady=4)
            ttk.Entry(g, textvariable=self._vars[key], width=14).grid(
                row=idx // 2, column=(idx % 2) * 2 + 1, sticky="w", padx=(8, 24), pady=4
            )

        c2 = self._card(tab, "Session & Configuration Data")
        tk.Label(
            c2,
            text=f"Settings & history directory: {CONFIG_DIR}",
            bg="#FFFFFF",
            fg="#5A697E",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(0, 8))
        btns = tk.Frame(c2, bg="#FFFFFF")
        btns.pack(fill="x")
        ttk.Button(btns, text="Save Settings Now", style="Accent.TButton", command=self._apply_only).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btns, text="Export Settings…", command=self._export_settings).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Import Settings…", command=self._import_settings).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Open Config Folder", command=WindowsPlatformService.open_config_folder).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btns, text="Reset Session Totals", command=self.on_reset_totals).pack(side="left")

    def _update_opacity_lbl(self) -> None:
        try:
            self._op_label.configure(text=f"{int(float(self._vars['opacity'].get()))}%")
        except (ValueError, tk.TclError):
            pass

    @staticmethod
    def _contrast_fg(hex_color: str) -> str:
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            return "#111827" if lum > 150 else "#FFFFFF"
        except Exception:
            return "#FFFFFF"

    def _pick_color(self, key: str) -> None:
        picked = colorchooser.askcolor(getattr(self._working, key), parent=self.win)[1]
        if picked:
            setattr(self._working, key, picked)
            btn = self._color_buttons.get(key)
            if btn:
                btn.configure(bg=picked, fg=self._contrast_fg(picked))

    def _apply_theme_preset(self, theme_name: str) -> None:
        self._working.apply_theme(theme_name)
        for key, btn in self._color_buttons.items():
            if not key.startswith("taskbar_"):
                val = getattr(self._working, key)
                btn.configure(bg=val, fg=self._contrast_fg(val))

    def _collect_settings(self) -> Settings:
        s = Settings(**asdict(self._working))
        s.adapter = str(self._vars["adapter"].get())
        s.show_virtual_adapters = bool(self._vars["show_virtual_adapters"].get())
        s.interval = float(self._vars["interval"].get())
        s.unit_mode = str(self._vars["unit_mode"].get())
        s.precision = int(self._vars["precision"].get())
        s.start_with_windows = bool(self._vars["start_with_windows"].get())
        s.auto_hide_fullscreen = bool(self._vars["auto_hide_fullscreen"].get())
        s.track_history = bool(self._vars["track_history"].get())

        s.show_main_window = bool(self._vars["show_main_window"].get())
        s.skin = str(self._vars["skin"].get())
        s.compact = bool(self._vars["compact"].get())
        s.font = str(self._vars["font"].get())
        s.font_size = int(self._vars["font_size"].get())
        s.opacity = round(float(self._vars["opacity"].get()) / 100.0, 2)
        s.show_download = bool(self._vars["show_download"].get())
        s.show_upload = bool(self._vars["show_upload"].get())
        s.show_totals = bool(self._vars["show_totals"].get())
        s.show_system_stats = bool(self._vars["show_system_stats"].get())
        s.show_power_watts = bool(self._vars["show_power_watts"].get())
        s.show_sparkline = bool(self._vars["show_sparkline"].get())
        s.show_adapter_name = bool(self._vars["show_adapter_name"].get())
        s.always_on_top = bool(self._vars["always_on_top"].get())
        s.lock_position = bool(self._vars["lock_position"].get())
        s.mouse_penetrate = bool(self._vars["mouse_penetrate"].get())
        s.dock_to_taskbar = bool(self._vars["dock_to_taskbar"].get())
        s.dock_side = str(self._vars["dock_side"].get())

        s.show_taskbar_window = bool(self._vars["show_taskbar_window"].get())
        s.taskbar_side = str(self._vars["taskbar_side"].get())
        s.taskbar_offset_x = int(self._vars["taskbar_offset_x"].get())
        s.taskbar_layout = str(self._vars["taskbar_layout"].get())
        s.taskbar_auto_theme = bool(self._vars["taskbar_auto_theme"].get())
        s.taskbar_font_size = int(self._vars["taskbar_font_size"].get())
        s.taskbar_show_download = bool(self._vars["taskbar_show_download"].get())
        s.taskbar_show_upload = bool(self._vars["taskbar_show_upload"].get())
        s.taskbar_show_cpu = bool(self._vars["taskbar_show_cpu"].get())
        s.taskbar_show_ram = bool(self._vars["taskbar_show_ram"].get())
        s.taskbar_show_power_watts = bool(self._vars["taskbar_show_power_watts"].get())

        s.label_download = str(self._vars["label_download"].get()) or "↓"
        s.label_upload = str(self._vars["label_upload"].get()) or "↑"
        s.label_cpu = str(self._vars["label_cpu"].get()) or "CPU"
        s.label_ram = str(self._vars["label_ram"].get()) or "RAM"
        s.label_power = str(self._vars["label_power"].get()) or "PWR"
        return s

    def _apply_only(self) -> bool:
        try:
            updated = self._collect_settings()
        except ValueError:
            messagebox.showerror(APP_NAME, "Please check that all numeric values are valid.", parent=self.win)
            return False
        self.on_apply(updated)
        self._working = Settings(**asdict(updated))
        if hasattr(self, "_save_status"):
            self._save_status.configure(text="All changes saved")
        return True

    def _export_settings(self) -> None:
        try:
            current = self._collect_settings()
        except ValueError:
            messagebox.showerror(APP_NAME, "Please check that all numeric values are valid.", parent=self.win)
            return
        path_str = filedialog.asksaveasfilename(
            parent=self.win,
            title="Export Speedometer Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="speedometer-settings.json",
        )
        if not path_str:
            return
        SettingsRepository(Path(path_str)).save(current)
        if hasattr(self, "_save_status"):
            self._save_status.configure(text="Settings exported")

    def _import_settings(self) -> None:
        path_str = filedialog.askopenfilename(
            parent=self.win,
            title="Import Speedometer Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path_str:
            return
        imported = SettingsRepository(Path(path_str)).load()
        self.on_apply(imported)
        self.win.destroy()

    def _ok(self) -> None:
        if self._apply_only():
            self.win.destroy()

    def _reset_defaults(self) -> None:
        if not messagebox.askyesno(APP_NAME, "Reset all options to their default values?", parent=self.win):
            return
        defaults = Settings()
        self.on_apply(defaults)
        self.win.destroy()


class ConnectionDetailsDialog:
    """TrafficMonitor-style Network Connection Details dialog."""

    def __init__(self, parent: tk.Tk, current_adapter: str, icon_photo=None) -> None:
        self.win = _make_dialog(parent, "Connection Details", 540, 480, icon_photo)
        self._adapters: list[AdapterInfo] = []
        self._selected = tk.StringVar(value=current_adapter)
        self._fields: dict[str, tk.Label] = {}
        self._build()
        self._refresh()

    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()

    def _build(self) -> None:
        hdr = tk.Frame(self.win, bg="#162032", padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Network Connection Details", bg="#162032", fg="#FFFFFF", font=("Segoe UI", 12, "bold")).pack(
            side="left"
        )

        top = tk.Frame(self.win, bg="#F5F7FB", padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="Interface:", bg="#F5F7FB", fg="#162032", font=("Segoe UI", 9, "bold")).pack(side="left")
        self._combo = ttk.Combobox(top, textvariable=self._selected, state="readonly", width=38)
        self._combo.pack(side="left", padx=(8, 8), fill="x", expand=True)
        self._combo.bind("<<ComboboxSelected>>", lambda _e: self._render_selected())
        ttk.Button(top, text="Refresh", command=self._refresh).pack(side="right")

        card = tk.Frame(self.win, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=16, pady=12)
        card.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        rows = (
            ("status", "Connection Status"),
            ("speed", "Link Speed"),
            ("mtu", "MTU"),
            ("ipv4", "IPv4 Address"),
            ("ipv6", "IPv6 Address"),
            ("mac", "Physical (MAC) Address"),
            ("recv_bytes", "Total Bytes Received"),
            ("sent_bytes", "Total Bytes Sent"),
            ("packets", "Packets (Recv / Sent)"),
            ("errors", "Errors / Drops (In / Out)"),
        )
        for idx, (key, title) in enumerate(rows):
            tk.Label(card, text=title, bg="#FFFFFF", fg="#5A697E", font=("Segoe UI", 9)).grid(
                row=idx, column=0, sticky="w", pady=5
            )
            val = tk.Label(card, text="-", bg="#FFFFFF", fg="#162032", font=("Consolas", 9), anchor="e")
            val.grid(row=idx, column=1, sticky="e", pady=5)
            self._fields[key] = val

        footer = tk.Frame(self.win, bg="#F5F7FB", padx=14, pady=8)
        footer.pack(fill="x")
        ttk.Button(footer, text="Copy Details", command=self._copy_details).pack(side="left")
        ttk.Button(footer, text="Close", style="Accent.TButton", command=self.win.destroy).pack(side="right")

    def _refresh(self) -> None:
        self._adapters = NetworkSampler.adapter_details()
        names = [a.name for a in self._adapters]
        self._combo.configure(values=names)
        if names and self._selected.get() not in names:
            up_first = next((a.name for a in self._adapters if a.is_up and not a.is_virtual), names[0])
            self._selected.set(up_first)
        self._render_selected()

    def _current(self) -> AdapterInfo | None:
        name = self._selected.get()
        return next((a for a in self._adapters if a.name == name), None)

    def _render_selected(self) -> None:
        info = self._current()
        if not info:
            return
        status_text = "Connected (Up)" if info.is_up else "Disconnected (Down)"
        if info.is_virtual:
            status_text += "  [Virtual]"
        self._fields["status"].configure(text=status_text, fg="#087F5B" if info.is_up else "#B91C1C")
        self._fields["speed"].configure(text=f"{info.speed_mbps} Mbps" if info.speed_mbps > 0 else "Unknown")
        self._fields["mtu"].configure(text=str(info.mtu))
        self._fields["ipv4"].configure(text=info.ipv4)
        self._fields["ipv6"].configure(text=info.ipv6[:40] + ("…" if len(info.ipv6) > 40 else ""))
        self._fields["mac"].configure(text=info.mac)
        self._fields["recv_bytes"].configure(text=format_total(info.bytes_recv))
        self._fields["sent_bytes"].configure(text=format_total(info.bytes_sent))
        self._fields["packets"].configure(text=f"{info.packets_recv:,}  /  {info.packets_sent:,}")
        self._fields["errors"].configure(text=f"{info.errin + info.dropin:,}  /  {info.errout + info.dropout:,}")

    def _copy_details(self) -> None:
        info = self._current()
        if not info:
            return
        text = (
            f"Adapter: {info.name}\n"
            f"Status: {'Up' if info.is_up else 'Down'}\n"
            f"Link Speed: {info.speed_mbps} Mbps\n"
            f"IPv4: {info.ipv4}\n"
            f"IPv6: {info.ipv6}\n"
            f"MAC: {info.mac}\n"
            f"Received: {format_total(info.bytes_recv)} | Sent: {format_total(info.bytes_sent)}"
        )
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        messagebox.showinfo(APP_NAME, "Adapter details copied to clipboard.", parent=self.win)


class TrafficHistoryDialog:
    """TrafficMonitor-style Historical Traffic Statistics dialog with chart & CSV export."""

    def __init__(self, parent: tk.Tk, history: TrafficHistoryRepository, icon_photo=None) -> None:
        self.history = history
        self.win = _make_dialog(parent, "Historical Traffic Statistics", 680, 540, icon_photo)
        self._kpi_labels: dict[str, tk.Label] = {}
        self._build()
        self._reload()

    def show(self) -> None:
        self._reload()
        self.win.deiconify()
        self.win.lift()

    def _build(self) -> None:
        hdr = tk.Frame(self.win, bg="#162032", padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="Historical Traffic Statistics",
            bg="#162032",
            fg="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        # KPI cards row
        kpi_row = tk.Frame(self.win, bg="#F5F7FB", padx=12, pady=10)
        kpi_row.pack(fill="x")
        for col, (key, title) in enumerate(
            (("today", "Today"), ("week", "Last 7 Days"), ("month", "This Month"), ("all_time", "All Time"))
        ):
            kpi_row.grid_columnconfigure(col, weight=1)
            card = tk.Frame(kpi_row, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=10, pady=8)
            card.grid(row=0, column=col, sticky="ew", padx=4)
            tk.Label(card, text=title, bg="#FFFFFF", fg="#5A697E", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            total_lbl = tk.Label(card, text="0 B", bg="#FFFFFF", fg="#162032", font=("Segoe UI", 12, "bold"))
            total_lbl.pack(anchor="w", pady=(2, 1))
            sub_lbl = tk.Label(card, text="↓ 0 B  ↑ 0 B", bg="#FFFFFF", fg="#5A697E", font=("Segoe UI", 8))
            sub_lbl.pack(anchor="w")
            self._kpi_labels[f"{key}_total"] = total_lbl
            self._kpi_labels[f"{key}_sub"] = sub_lbl

        # 14-day chart
        chart_wrap = tk.Frame(self.win, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=10, pady=8)
        chart_wrap.pack(fill="x", padx=16, pady=(0, 8))
        chart_hdr = tk.Frame(chart_wrap, bg="#FFFFFF")
        chart_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(chart_hdr, text="Last 14 Days (Download vs Upload)", bg="#FFFFFF", fg="#162032", font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )
        tk.Label(chart_hdr, text="■ Download   ■ Upload", bg="#FFFFFF", fg="#5A697E", font=("Segoe UI", 8)).pack(side="right")
        self._chart = tk.Canvas(chart_wrap, height=110, bg="#FAFBFD", highlightthickness=0)
        self._chart.pack(fill="x")

        # Daily table
        table_wrap = tk.Frame(self.win, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1)
        table_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        cols = ("date", "download", "upload", "total")
        self._tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=8)
        for cid, heading, anchor, width in (
            ("date", "Date", "w", 130),
            ("download", "Download", "e", 150),
            ("upload", "Upload", "e", 150),
            ("total", "Total", "e", 160),
        ):
            self._tree.heading(cid, text=heading)
            self._tree.column(cid, anchor=anchor, width=width)
        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        footer = tk.Frame(self.win, bg="#F5F7FB", padx=16, pady=8)
        footer.pack(fill="x")
        ttk.Button(footer, text="Export CSV…", command=self._export_csv).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="Clear History", command=self._clear_history).pack(side="left")
        ttk.Button(footer, text="Close", style="Accent.TButton", command=self.win.destroy).pack(side="right")

    def _reload(self) -> None:
        summary = self.history.summary()
        for key in ("today", "week", "month", "all_time"):
            down, up = summary[key]
            self._kpi_labels[f"{key}_total"].configure(text=format_total(down + up))
            self._kpi_labels[f"{key}_sub"].configure(text=f"↓ {format_total(down)}  ↑ {format_total(up)}")

        for row_id in self._tree.get_children():
            self._tree.delete(row_id)
        for rec in self.history.records_descending():
            self._tree.insert(
                "",
                "end",
                values=(
                    rec.date,
                    format_total(rec.download_bytes),
                    format_total(rec.upload_bytes),
                    format_total(rec.total_bytes),
                ),
            )
        self._draw_chart()

    def _draw_chart(self) -> None:
        self._chart.update_idletasks()
        c = self._chart
        c.delete("all")
        w = max(c.winfo_width(), 580)
        h = max(c.winfo_height(), 110)
        records = self.history.recent_days(14)
        peak = max((max(r.download_bytes, r.upload_bytes) for r in records), default=1) or 1

        pad_l, pad_r, pad_t, pad_b = 12, 12, 10, 22
        usable_w = w - pad_l - pad_r
        usable_h = h - pad_t - pad_b
        group_w = usable_w / len(records)
        bar_w = max(4, (group_w - 10) / 2)

        c.create_line(pad_l, h - pad_b, w - pad_r, h - pad_b, fill="#DCE3EE")
        for idx, rec in enumerate(records):
            gx = pad_l + idx * group_w + 5
            dh = (rec.download_bytes / peak) * usable_h
            uh = (rec.upload_bytes / peak) * usable_h
            if dh > 0:
                c.create_rectangle(gx, h - pad_b - dh, gx + bar_w, h - pad_b, fill="#10B981", outline="")
            if uh > 0:
                c.create_rectangle(gx + bar_w + 2, h - pad_b - uh, gx + bar_w * 2 + 2, h - pad_b, fill="#3B82F6", outline="")
            c.create_text(gx + bar_w, h - 10, text=rec.date[5:], fill="#5A697E", font=("Segoe UI", 7))

    def _export_csv(self) -> None:
        path_str = filedialog.asksaveasfilename(
            parent=self.win,
            title="Export Traffic History",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="speedometer-traffic-history.csv",
        )
        if not path_str:
            return
        self.history.export_csv(Path(path_str))
        messagebox.showinfo(APP_NAME, f"Exported history to:\n{path_str}", parent=self.win)

    def _clear_history(self) -> None:
        if messagebox.askyesno(APP_NAME, "Delete all recorded daily traffic statistics?", parent=self.win):
            self.history.clear()
            self._reload()
