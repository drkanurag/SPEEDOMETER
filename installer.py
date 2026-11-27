"""Per-user installer for Speedometer.

This is intentionally a small, no-admin installer. It copies the packaged
application into LocalAppData, creates standard Windows shortcuts, and can
register the installed EXE to start at sign-in.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

APP_NAME = "Speedometer"
INSTALL_DIR = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
CONFIG_FILE = Path(os.environ["APPDATA"]) / APP_NAME / "settings.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def special_folder(csidl: int) -> Path:
    path = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, path)
    return Path(path.value)


def set_startup(executable: Path, enabled: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{executable}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def create_shortcut(shortcut: Path, executable: Path) -> None:
    """Use Windows Script Host to create an ordinary .lnk file."""
    from win32com.client import Dispatch

    shortcut.parent.mkdir(parents=True, exist_ok=True)
    link = Dispatch("WScript.Shell").CreateShortcut(str(shortcut))
    link.TargetPath = str(executable)
    link.WorkingDirectory = str(executable.parent)
    link.IconLocation = str(executable)
    link.Description = "Live network & system monitor for Windows 11"
    link.Save()


class Installer:
    def __init__(self) -> None:
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("Install Speedometer")
        self.root.resizable(False, False)
        self.root.configure(bg="#F5F7FB")
        self.startup = tk.BooleanVar(value=True)
        self.launch = tk.BooleanVar(value=True)
        self.desktop = tk.BooleanVar(value=True)
        self._configure_style()
        self._build()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCheckbutton", background="#FFFFFF", foreground="#162032", font=("Segoe UI", 9))
        style.configure("TButton", background="#E9EEF6", foreground="#162032", borderwidth=0, padding=[12, 5])
        style.configure(
            "Accent.TButton",
            background="#1D63DC",
            foreground="#FFFFFF",
            borderwidth=0,
            padding=[16, 5],
            font=("Segoe UI", 9, "bold"),
        )

    def _build(self) -> None:
        hdr = tk.Frame(self.root, bg="#162032", padx=24, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Speedometer Setup", font=("Segoe UI", 16, "bold"), bg="#162032", fg="#FFFFFF").pack(anchor="w")
        tk.Label(
            hdr,
            text="Lightweight live network, CPU & RAM monitor for Windows 11",
            font=("Segoe UI", 9),
            bg="#162032",
            fg="#9DB1CE",
        ).pack(anchor="w", pady=(2, 0))

        box = tk.Frame(self.root, bg="#F5F7FB", padx=22, pady=18)
        box.pack(fill="both", expand=True)

        path_card = tk.Frame(box, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=12, pady=10)
        path_card.pack(fill="x", pady=(0, 12))
        tk.Label(path_card, text="Install Location (Per-User)", bg="#FFFFFF", fg="#5A697E", font=("Segoe UI", 8, "bold")).pack(
            anchor="w"
        )
        tk.Label(path_card, text=str(INSTALL_DIR), bg="#FFFFFF", fg="#162032", font=("Consolas", 9)).pack(
            anchor="w", pady=(2, 0)
        )

        opts_card = tk.Frame(box, bg="#FFFFFF", highlightbackground="#DCE3EE", highlightthickness=1, padx=12, pady=10)
        opts_card.pack(fill="x")
        ttk.Checkbutton(opts_card, text="Start Speedometer when I sign in to Windows", variable=self.startup).pack(
            anchor="w", pady=2
        )
        ttk.Checkbutton(opts_card, text="Create a Desktop shortcut", variable=self.desktop).pack(anchor="w", pady=2)
        ttk.Checkbutton(opts_card, text="Launch Speedometer after installation", variable=self.launch).pack(
            anchor="w", pady=2
        )

        self.status = tk.Label(box, text="Ready to install.", bg="#F5F7FB", fg="#5A697E", font=("Segoe UI", 9))
        self.status.pack(anchor="w", pady=(12, 0))

        controls = tk.Frame(box, bg="#F5F7FB")
        controls.pack(fill="x", pady=(14, 0))
        ttk.Button(controls, text="Cancel", command=self.root.destroy).pack(side="right")
        self.install_button = ttk.Button(controls, text="Install", style="Accent.TButton", command=self.install)
        self.install_button.pack(side="right", padx=(0, 8))

    def install(self) -> None:
        packaged = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "Speedometer.exe"
        if not packaged.exists():
            messagebox.showerror(APP_NAME, "The application package is missing. Please download the installer again.")
            return
        self.install_button.configure(state="disabled")
        self.status.configure(text="Installing…")
        self.root.update_idletasks()
        target = INSTALL_DIR / "Speedometer.exe"
        try:
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(packaged, target)
            start_menu = special_folder(0x0B) / APP_NAME / f"{APP_NAME}.lnk"
            create_shortcut(start_menu, target)
            if self.desktop.get():
                create_shortcut(special_folder(0x10) / f"{APP_NAME}.lnk", target)
            set_startup(target, self.startup.get())
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                settings = {}
            settings["start_with_windows"] = self.startup.get()
            CONFIG_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        except OSError as error:
            self.install_button.configure(state="normal")
            self.status.configure(text="Installation could not finish.")
            messagebox.showerror(APP_NAME, f"Could not install Speedometer:\n{error}")
            return
        if self.launch.get():
            subprocess.Popen([str(target)], close_fds=True)
        messagebox.showinfo(
            APP_NAME,
            "Speedometer has been installed.\n\nRight-click the floating monitor or tray icon for Options, Taskbar Window, and Traffic History.",
        )
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Installer().run()
