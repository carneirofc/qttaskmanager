"""App Data viewer — enumerate per-application data folders under the standard
Windows AppData roots so they can be browsed and opened. READ-ONLY: this only
reports sizes and locations; navigation/inspection happens via Explorer.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event

from .scan_data import human_size, dir_size, SEV_INFO


def _roots() -> list[tuple[str, str]]:
    env = os.environ.get
    userprofile = env("USERPROFILE", "")
    roots = [
        ("Roaming", env("APPDATA", "")),
        ("Local", env("LOCALAPPDATA", "")),
        ("LocalLow", os.path.join(userprofile, "AppData", "LocalLow") if userprofile else ""),
        ("ProgramData", env("ProgramData", r"C:\ProgramData")),
    ]
    return roots


def _is_app_dir(entry) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False) and not entry.is_junction()
    except OSError:
        return False


def scan_appdata(cancel: Event, progress: Callable[[str], None]) -> list[dict]:
    rows: list[dict] = []
    for label, root in _roots():
        if cancel.is_set():
            break
        if not root or not os.path.isdir(root):
            continue
        try:
            with os.scandir(root) as it:
                apps = [e for e in it if _is_app_dir(e)]
        except OSError:
            continue

        for entry in apps:
            if cancel.is_set():
                break
            progress(f"{label}: {entry.name}…")
            size, files, _skipped = dir_size(entry.path, cancel, progress)
            rows.append({
                "app":        entry.name,
                "root":       label,
                "path":       entry.path,
                "size_h":     human_size(size),
                "size_bytes": size,
                "items":      files,
                "severity":   SEV_INFO,
            })
    return rows
