r"""Registry hygiene scan (READ-ONLY) using stdlib winreg.

Reports registry entries that point at files/locations that no longer exist:
  - Startup entries  : HKCU/HKLM Run & RunOnce
  - App Paths        : HKLM/HKCU ...\App Paths
  - Uninstall        : HKLM/HKCU ...\Uninstall (orphaned install locations)

Nothing is written or deleted. Detection is deliberately conservative — only
*absolute* paths that are confidently missing are flagged, and host launchers,
Store/MSI-advertised entries and inaccessible keys are skipped to keep false
positives near zero.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event

import winreg

from .scan_data import (
    expand, extract_exe, is_store_or_virtual, is_host_launcher, path_missing,
    SEV_BROKEN,
)

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

# (root, label, view-flag) — HKLM is scanned in both registry views.
_HIVES = [
    (HKCU, "HKCU", 0),
    (HKLM, "HKLM (64-bit)", winreg.KEY_WOW64_64KEY),
    (HKLM, "HKLM (32-bit)", winreg.KEY_WOW64_32KEY),
]

_RUN_KEYS = [
    r"Software\Microsoft\Windows\CurrentVersion\Run",
    r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
]
_APP_PATHS = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
_UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


# ── winreg helpers ────────────────────────────────────────────────────────────

def _open(root, subkey, view):
    return winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view)


def _values(key):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumValue(key, i))  # (name, data, type)
        except OSError:
            break
        i += 1
    return out


def _subkeys(key):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumKey(key, i))
        except OSError:
            break
        i += 1
    return out


def _try_value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _icon_path(icon: str) -> str:
    """Extract the file path from a DisplayIcon value of the form  path,index.

    Parsed precisely (not via extract_exe) so unquoted paths containing spaces
    and no .exe — e.g. '...\\User Data\\...\\icon.ico,0' — are not truncated.
    """
    raw = icon.strip()
    if "," in raw:
        head, tail = raw.rsplit(",", 1)
        if tail.strip().lstrip("-").isdigit():   # trailing icon index
            raw = head
    return raw.strip().strip('"')


# ── individual scans ──────────────────────────────────────────────────────────

def _scan_run(root, label, view, cancel) -> list[dict]:
    rows = []
    for subkey in _RUN_KEYS:
        if cancel.is_set():
            break
        try:
            key = _open(root, subkey, view)
        except OSError:
            continue
        with key:
            for name, data, _typ in _values(key):
                if not isinstance(data, str):
                    continue
                exe = expand(extract_exe(data))
                if not exe or is_host_launcher(exe) or is_store_or_virtual(exe):
                    continue
                if os.path.isabs(exe) and path_missing(exe):
                    rows.append({
                        "category": "Startup (Run)",
                        "hive": label, "name": name, "target": exe,
                        "issue": "Target file is missing",
                        "severity": SEV_BROKEN,
                        "keypath": f"{label}\\{subkey}",
                    })
    return rows


def _scan_app_paths(root, label, view, cancel) -> list[dict]:
    rows = []
    try:
        root_key = _open(root, _APP_PATHS, view)
    except OSError:
        return rows
    with root_key:
        for sub in _subkeys(root_key):
            if cancel.is_set():
                break
            try:
                k = _open(root, _APP_PATHS + "\\" + sub, view)
            except OSError:
                continue
            with k:
                default = _try_value(k, "")  # (Default) value = full exe path
            exe = expand(extract_exe(default)) if isinstance(default, str) else ""
            if not exe or is_store_or_virtual(exe) or not os.path.isabs(exe):
                continue
            if path_missing(exe):
                rows.append({
                    "category": "App Paths",
                    "hive": label, "name": sub, "target": exe,
                    "issue": "Registered application is missing",
                    "severity": SEV_BROKEN,
                    "keypath": f"{label}\\{_APP_PATHS}\\{sub}",
                })
    return rows


def _scan_uninstall(root, label, view, cancel) -> list[dict]:
    rows = []
    try:
        root_key = _open(root, _UNINSTALL, view)
    except OSError:
        return rows
    with root_key:
        for sub in _subkeys(root_key):
            if cancel.is_set():
                break
            try:
                k = _open(root, _UNINSTALL + "\\" + sub, view)
            except OSError:
                continue
            with k:
                name = _try_value(k, "DisplayName") or sub
                install = _try_value(k, "InstallLocation")
                icon = _try_value(k, "DisplayIcon")

            # Pick a concrete path to verify: prefer InstallLocation (a dir),
            # else the icon path. Skip when neither is concrete (e.g. pure
            # msiexec /X{GUID} entries) to avoid false positives.
            target = ""
            if isinstance(install, str) and install.strip():
                target = expand(install.strip().strip('"'))
            elif isinstance(icon, str) and icon.strip():
                target = expand(_icon_path(icon))

            if not target or is_store_or_virtual(target) or not os.path.isabs(target):
                continue
            if path_missing(target):
                rows.append({
                    "category": "Uninstall",
                    "hive": label, "name": str(name), "target": target,
                    "issue": "Install location no longer exists",
                    "severity": SEV_BROKEN,
                    "keypath": f"{label}\\{_UNINSTALL}\\{sub}",
                })
    return rows


# ── entry point ───────────────────────────────────────────────────────────────

def scan_registry(cancel: Event, progress: Callable[[str], None]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()

    stages = [
        ("startup entries", _scan_run),
        ("App Paths", _scan_app_paths),
        ("uninstall entries", _scan_uninstall),
    ]
    for desc, fn in stages:
        if cancel.is_set():
            break
        progress(f"Checking {desc}…")
        for root, label, view in _HIVES:
            if cancel.is_set():
                break
            # HKCU is identical across views — scan it only once.
            if root == HKCU and view != 0:
                continue
            for row in fn(root, label, view, cancel):
                dedup = (row["category"], row["name"], row["target"])
                if dedup not in seen:
                    seen.add(dedup)
                    rows.append(row)
    return rows
