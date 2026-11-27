"""Reusable visual widgets, icon rendering, and modern ttk styling."""

from __future__ import annotations

import tkinter as tk
from collections import deque
from tkinter import ttk

from PIL import Image, ImageDraw


def create_app_icon(size: int = 64) -> Image.Image:
    """Create a crisp TrafficMonitor-style dual-arrow speed badge icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(2, size // 16)
    radius = max(6, size // 4)
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=radius,
        fill="#141A26",
        outline="#2E3B52",
        width=max(1, size // 32),
    )

    # Download arrow (left, emerald)
    cx1 = int(size * 0.36)
    top_y = int(size * 0.24)
    bot_y = int(size * 0.76)
    w = max(2, size // 14)
    head = max(4, size // 6)
    draw.rectangle((cx1 - w // 2, top_y, cx1 + w // 2, bot_y - head // 2), fill="#3FE0A8")
    draw.polygon(
        [(cx1 - head, bot_y - head), (cx1 + head, bot_y - head), (cx1, bot_y)],
        fill="#3FE0A8",
    )

    # Upload arrow (right, sky blue)
    cx2 = int(size * 0.65)
    draw.rectangle((cx2 - w // 2, top_y + head // 2, cx2 + w // 2, bot_y), fill="#69B1FF")
    draw.polygon(
        [(cx2 - head, top_y + head), (cx2 + head, top_y + head), (cx2, top_y)],
        fill="#69B1FF",
    )
    return img


def configure_ttk_theme(root: tk.Misc) -> None:
    """Apply a clean, modern Windows 11-inspired ttk theme for dialogs."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        return

    bg = "#F5F7FB"
    surface = "#FFFFFF"
    border = "#D5DCE6"
    fg = "#162032"
    muted = "#5A697E"
    accent = "#1D63DC"
    accent_hover = "#1552BD"

    style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 9))
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=surface, relief="flat")
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 8))
    style.configure("Section.TLabel", background=surface, foreground=fg, font=("Segoe UI", 10, "bold"))
    style.configure("CardLabel.TLabel", background=surface, foreground=fg)
    style.configure("CardMuted.TLabel", background=surface, foreground=muted, font=("Segoe UI", 8))

    style.configure(
        "TNotebook",
        background=bg,
        borderwidth=0,
        tabmargins=[2, 4, 2, 0],
    )
    style.configure(
        "TNotebook.Tab",
        background="#E8EDF5",
        foreground="#3B495E",
        padding=[14, 6],
        borderwidth=0,
        font=("Segoe UI", 9),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", surface), ("active", "#DFE6F2")],
        foreground=[("selected", accent), ("active", fg)],
        font=[("selected", ("Segoe UI", 9, "bold"))],
    )

    style.configure(
        "TButton",
        background="#E9EEF6",
        foreground=fg,
        borderwidth=0,
        padding=[12, 5],
        font=("Segoe UI", 9),
    )
    style.map(
        "TButton",
        background=[("active", "#DCE4F0"), ("pressed", "#CFD9E8")],
    )

    style.configure(
        "Accent.TButton",
        background=accent,
        foreground="#FFFFFF",
        borderwidth=0,
        padding=[14, 5],
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", accent_hover), ("pressed", "#104199")],
        foreground=[("disabled", "#C8D6F0")],
    )

    style.configure(
        "TCheckbutton",
        background=surface,
        foreground=fg,
        font=("Segoe UI", 9),
    )
    style.map("TCheckbutton", background=[("active", surface)])

    style.configure(
        "TRadiobutton",
        background=surface,
        foreground=fg,
        font=("Segoe UI", 9),
    )
    style.map("TRadiobutton", background=[("active", surface)])

    style.configure(
        "TCombobox",
        fieldbackground=surface,
        background="#E9EEF6",
        bordercolor=border,
        arrowcolor=fg,
        padding=4,
    )

    style.configure(
        "Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=fg,
        rowheight=24,
        bordercolor=border,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Treeview.Heading",
        background="#EDF2F8",
        foreground=fg,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        padding=[6, 5],
    )
    style.map("Treeview", background=[("selected", "#DCE8FC")], foreground=[("selected", "#12326B")])


class SparklineCanvas(tk.Canvas):
    """Lightweight dual-series throughput sparkline for download and upload history."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 190,
        height: int = 28,
        bg: str = "#1B2230",
        down_color: str = "#3FE0A8",
        up_color: str = "#69B1FF",
        grid_color: str = "#2A3447",
        max_points: int = 36,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self._down: deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._up: deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._down_color = down_color
        self._up_color = up_color
        self._grid_color = grid_color

    def set_colors(self, bg: str, down_color: str, up_color: str, grid_color: str) -> None:
        self.configure(bg=bg)
        self._down_color = down_color
        self._up_color = up_color
        self._grid_color = grid_color
        self._redraw()

    def push(self, down_bps: float, up_bps: float) -> None:
        self._down.append(max(0.0, down_bps))
        self._up.append(max(0.0, up_bps))
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w = max(int(self.winfo_reqwidth()), self.winfo_width())
        h = max(int(self.winfo_reqheight()), self.winfo_height())
        if w < 10 or h < 6:
            return

        # Subtle baseline and midpoint guide
        self.create_line(0, h - 1, w, h - 1, fill=self._grid_color, width=1)
        self.create_line(0, h // 2, w, h // 2, fill=self._grid_color, width=1, dash=(2, 3))

        peak = max(max(self._down, default=0.0), max(self._up, default=0.0), 1024.0)
        count = len(self._down)
        if count < 2:
            return

        step = (w - 2) / (count - 1)
        pad_top = 3
        usable_h = max(h - pad_top - 2, 2)

        def build_coords(series: deque[float]) -> list[float]:
            coords: list[float] = []
            for idx, val in enumerate(series):
                x = 1 + idx * step
                ratio = min(val / peak, 1.0)
                y = (h - 2) - ratio * usable_h
                coords.extend((x, y))
            return coords

        up_coords = build_coords(self._up)
        down_coords = build_coords(self._down)
        if len(up_coords) >= 4:
            self.create_line(*up_coords, fill=self._up_color, width=1.4, smooth=True)
        if len(down_coords) >= 4:
            self.create_line(*down_coords, fill=self._down_color, width=1.8, smooth=True)


class UsageBar(tk.Canvas):
    """Compact horizontal bar for CPU/RAM visualization."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 72,
        height: int = 5,
        track_color: str = "#2A3447",
        fill_color: str = "#3FE0A8",
        bg: str = "#12161F",
    ) -> None:
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self._track = track_color
        self._fill = fill_color
        self._percent = 0.0
        self.set_percent(0.0)

    def set_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.delete("all")
        w = max(int(self.winfo_reqwidth()), self.winfo_width())
        h = max(int(self.winfo_reqheight()), self.winfo_height())
        self.create_rectangle(0, 0, w, h, fill=self._track, outline="")
        fill_w = int((self._percent / 100.0) * w)
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=self._fill, outline="")
