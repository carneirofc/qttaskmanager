"""Disk-cleanup scan — enumerate well-known Windows junk/cache/temp locations
and report their size. READ-ONLY: nothing is ever deleted here.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event

from .scan_data import human_size, dir_size, SEV_OK, SEV_REVIEW

# (display name, path, default severity, note)
def _locations() -> list[tuple[str, str, str, str]]:
    env = os.environ.get
    local       = env("LOCALAPPDATA", "")
    appdata     = env("APPDATA", "")
    userprofile = env("USERPROFILE", "")
    windir      = env("SystemRoot", r"C:\Windows")
    programdata = env("ProgramData", r"C:\ProgramData")
    temp        = env("TEMP", "")

    j = os.path.join
    return [
        ("User Temp",               temp,
         SEV_OK,     "Per-user temporary files — generally safe to clear."),
        ("Windows Temp",            j(windir, "Temp"),
         SEV_OK,     "System temporary files — generally safe to clear."),
        ("Windows Update cache",    j(windir, "SoftwareDistribution", "Download"),
         SEV_REVIEW, "Downloaded update packages; safe once updates are installed."),
        ("Delivery Optimization",   j(windir, "SoftwareDistribution", "DeliveryOptimization"),
         SEV_REVIEW, "Peer-to-peer update cache — rebuilt as needed."),
        ("Prefetch",                j(windir, "Prefetch"),
         SEV_REVIEW, "App-launch optimisation data — rebuilt automatically."),
        ("Thumbnail / icon cache",  j(local, "Microsoft", "Windows", "Explorer"),
         SEV_OK,     "thumbcache_*.db / iconcache — rebuilt on demand."),
        ("Internet cache",          j(local, "Microsoft", "Windows", "INetCache"),
         SEV_OK,     "Cached web content (WinINet)."),
        ("Crash dumps",             j(local, "CrashDumps"),
         SEV_REVIEW, "Per-user application crash dumps."),
        ("Windows Error Reporting", j(programdata, "Microsoft", "Windows", "WER"),
         SEV_REVIEW, "Error-reporting queue and archive."),
        ("Kernel minidumps",        j(windir, "Minidump"),
         SEV_REVIEW, "Kernel crash minidumps."),
        ("Chrome cache",            j(local, "Google", "Chrome", "User Data", "Default", "Cache"),
         SEV_OK,     "Browser cache — rebuilt automatically."),
        ("Edge cache",              j(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
         SEV_OK,     "Browser cache — rebuilt automatically."),
        ("Firefox profiles",        j(appdata, "Mozilla", "Firefox", "Profiles"),
         SEV_REVIEW, "Includes cache *and* profile data — review before clearing."),
        ("Downloads",               j(userprofile, "Downloads"),
         SEV_REVIEW, "Your downloads — REVIEW; never bulk-delete blindly."),
        ("Recycle Bin",             "C:\\$Recycle.Bin",
         SEV_REVIEW, "Deleted items pending purge. Access may be limited."),
    ]

_REC = {SEV_OK: "Safe to clear", SEV_REVIEW: "Review first"}


def scan_disk_cleanup(cancel: Event, progress: Callable[[str], None]) -> list[dict]:
    rows: list[dict] = []
    for name, path, sev, note in _locations():
        if cancel.is_set():
            break
        if not path or not os.path.exists(path):
            continue  # don't clutter the report with locations that aren't present
        progress(f"Scanning: {name}…")

        try:
            if os.path.isfile(path):
                size, files, skipped = os.path.getsize(path), 1, 0
            else:
                size, files, skipped = dir_size(path, cancel, progress)
        except OSError:
            size, files, skipped = 0, 0, 1

        partial = " (partial — access limited)" if skipped else ""
        rows.append({
            "name":       name,
            "path":       path,
            "size_h":     human_size(size),
            "size_bytes": size,
            "file_count": files,
            "rec":        _REC.get(sev, "Review"),
            "severity":   sev,
            "note":       note + partial,
        })
    return rows
