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
    locallow    = j_safe(env("USERPROFILE", ""), "AppData", "LocalLow")
    appdata     = env("APPDATA", "")
    userprofile = env("USERPROFILE", "")
    windir      = env("SystemRoot", r"C:\Windows")
    sysdrive    = env("SystemDrive", "C:")
    programdata = env("ProgramData", r"C:\ProgramData")
    temp        = env("TEMP", "")

    j = os.path.join
    rows: list[tuple[str, str, str, str]] = []

    # ── Windows temp / system caches ──────────────────────────────────────────
    rows += [
        ("User Temp",               temp,
         SEV_OK,     "Per-user temporary files — generally safe to clear."),
        ("Windows Temp",            j(windir, "Temp"),
         SEV_OK,     "System temporary files — generally safe to clear."),
        ("Prefetch",                j(windir, "Prefetch"),
         SEV_REVIEW, "App-launch optimisation data — rebuilt automatically."),
        ("Font cache",              j(windir, "ServiceProfiles", "LocalService",
                                       "AppData", "Local", "FontCache"),
         SEV_OK,     "Font cache — rebuilt automatically."),
        ("Thumbnail / icon cache",  j(local, "Microsoft", "Windows", "Explorer"),
         SEV_OK,     "thumbcache_*.db / iconcache — rebuilt on demand."),
        ("Internet cache",          j(local, "Microsoft", "Windows", "INetCache"),
         SEV_OK,     "Cached web content (WinINet)."),
        ("Web cache (WebCacheV*)",  j(local, "Microsoft", "Windows", "WebCache"),
         SEV_REVIEW, "Explorer/Edge history & cookies database."),
        ("INetCache (LocalLow)",    j(locallow, "Microsoft", "Internet Explorer"),
         SEV_OK,     "Low-integrity browser cache."),
        ("Recent items",            j(appdata, "Microsoft", "Windows", "Recent"),
         SEV_REVIEW, "Recently-opened file shortcuts (jump lists)."),
        ("DirectX shader cache",    j(local, "D3DSCache"),
         SEV_OK,     "Compiled shader cache — rebuilt by games/apps."),
        ("NVIDIA shader cache",     j(local, "NVIDIA", "DXCache"),
         SEV_OK,     "GPU shader cache — rebuilt automatically."),
        ("NVIDIA GL cache",         j(local, "NVIDIA", "GLCache"),
         SEV_OK,     "OpenGL shader cache — rebuilt automatically."),
        ("AMD shader cache",        j(local, "AMD", "DxCache"),
         SEV_OK,     "GPU shader cache — rebuilt automatically."),
    ]

    # ── Windows Update / servicing ────────────────────────────────────────────
    rows += [
        ("Windows Update cache",    j(windir, "SoftwareDistribution", "Download"),
         SEV_REVIEW, "Downloaded update packages; safe once updates are installed."),
        ("Delivery Optimization",   j(windir, "SoftwareDistribution", "DeliveryOptimization"),
         SEV_REVIEW, "Peer-to-peer update cache — rebuilt as needed."),
        ("Windows.old",             j(sysdrive + os.sep, "Windows.old"),
         SEV_REVIEW, "Previous Windows install — needed to roll back an upgrade."),
        ("CBS logs",                j(windir, "Logs", "CBS"),
         SEV_REVIEW, "Component-servicing logs — large after updates."),
        ("Setup downloads (ESD)",   j(sysdrive + os.sep, "$WINDOWS.~BT"),
         SEV_REVIEW, "Upgrade staging — left over after a feature update."),
    ]

    # ── Crash dumps / error reporting ─────────────────────────────────────────
    rows += [
        ("Crash dumps",             j(local, "CrashDumps"),
         SEV_REVIEW, "Per-user application crash dumps."),
        ("Windows Error Reporting", j(programdata, "Microsoft", "Windows", "WER"),
         SEV_REVIEW, "Error-reporting queue and archive."),
        ("WER (per-user)",          j(local, "Microsoft", "Windows", "WER"),
         SEV_REVIEW, "Per-user error-reporting queue and archive."),
        ("Kernel minidumps",        j(windir, "Minidump"),
         SEV_REVIEW, "Kernel crash minidumps."),
        ("Full memory dump",        j(windir, "MEMORY.DMP"),
         SEV_REVIEW, "Kernel memory dump from the last crash — can be huge."),
        ("Windows Defender scans",  j(programdata, "Microsoft", "Windows Defender",
                                       "Scans", "History"),
         SEV_REVIEW, "Antivirus scan history — rebuilt over time."),
    ]

    # ── Browsers ──────────────────────────────────────────────────────────────
    # Chromium-family browsers keep several cache trees per profile; clear all.
    chromium = [
        ("Chrome",  j(local, "Google", "Chrome", "User Data")),
        ("Edge",    j(local, "Microsoft", "Edge", "User Data")),
        ("Brave",   j(local, "BraveSoftware", "Brave-Browser", "User Data")),
        ("Vivaldi", j(local, "Vivaldi", "User Data")),
        ("Opera",   j(appdata, "Opera Software", "Opera Stable")),
        ("Opera GX", j(appdata, "Opera Software", "Opera GX Stable")),
    ]
    for label, base in chromium:
        rows += [
            (f"{label} cache",        j(base, "Default", "Cache"),
             SEV_OK, "Browser cache — rebuilt automatically."),
            (f"{label} code cache",   j(base, "Default", "Code Cache"),
             SEV_OK, "Compiled-script cache — rebuilt automatically."),
            (f"{label} GPU cache",    j(base, "Default", "GPUCache"),
             SEV_OK, "GPU shader cache — rebuilt automatically."),
        ]
    rows += [
        ("Firefox profiles",        j(appdata, "Mozilla", "Firefox", "Profiles"),
         SEV_REVIEW, "Includes cache *and* profile data — review before clearing."),
        ("Firefox cache",           j(local, "Mozilla", "Firefox", "Profiles"),
         SEV_OK,     "Firefox on-disk cache — rebuilt automatically."),
    ]

    # ── Communication / media apps ────────────────────────────────────────────
    rows += [
        ("Teams cache",             j(appdata, "Microsoft", "Teams", "Cache"),
         SEV_OK,     "Classic Teams cache — rebuilt automatically."),
        ("Teams (new) cache",       j(local, "Packages",
                                       "MSTeams_8wekyb3d8bbwe", "LocalCache"),
         SEV_REVIEW, "New Teams local cache."),
        ("Discord cache",           j(appdata, "discord", "Cache"),
         SEV_OK,     "Discord cache — rebuilt automatically."),
        ("Slack cache",             j(appdata, "Slack", "Cache"),
         SEV_OK,     "Slack cache — rebuilt automatically."),
        ("Spotify cache",           j(local, "Spotify", "Storage"),
         SEV_OK,     "Streamed-audio cache — rebuilt automatically."),
        ("Zoom cache",              j(appdata, "Zoom", "data"),
         SEV_REVIEW, "Zoom local data and cache."),
    ]

    # ── Developer tool caches ─────────────────────────────────────────────────
    rows += [
        ("npm cache",               j(local, "npm-cache"),
         SEV_OK,     "Node package cache — re-downloaded on demand."),
        ("npm cache (roaming)",     j(appdata, "npm-cache"),
         SEV_OK,     "Node package cache — re-downloaded on demand."),
        ("Yarn cache",              j(local, "Yarn", "Cache"),
         SEV_OK,     "Yarn package cache — re-downloaded on demand."),
        ("pnpm store",              j(local, "pnpm", "store"),
         SEV_REVIEW, "pnpm content-addressable store — shared across projects."),
        ("pip cache",               j(local, "pip", "Cache"),
         SEV_OK,     "Python wheel cache — re-downloaded on demand."),
        ("uv cache",                j(local, "uv", "cache"),
         SEV_OK,     "uv package cache — re-downloaded on demand."),
        ("NuGet packages",          j(userprofile, ".nuget", "packages"),
         SEV_REVIEW, ".NET package cache — re-downloaded on demand."),
        ("Gradle cache",            j(userprofile, ".gradle", "caches"),
         SEV_REVIEW, "Gradle build cache — re-downloaded on demand."),
        ("Maven repository",        j(userprofile, ".m2", "repository"),
         SEV_REVIEW, "Maven local repo — re-downloaded on demand."),
        ("Go module cache",         j(userprofile, "go", "pkg", "mod"),
         SEV_REVIEW, "Go module cache — re-downloaded on demand."),
        ("Cargo registry",         j(userprofile, ".cargo", "registry"),
         SEV_REVIEW, "Rust crate cache — re-downloaded on demand."),
        ("VS Code cache",           j(appdata, "Code", "Cache"),
         SEV_OK,     "Editor cache — rebuilt automatically."),
        ("VS Code CachedData",      j(appdata, "Code", "CachedData"),
         SEV_OK,     "Compiled-extension cache — rebuilt automatically."),
    ]

    # ── Cloud installers / misc ───────────────────────────────────────────────
    rows += [
        ("Downloads",               j(userprofile, "Downloads"),
         SEV_REVIEW, "Your downloads — REVIEW; never bulk-delete blindly."),
        ("Recycle Bin",             sysdrive + r"\$Recycle.Bin",
         SEV_REVIEW, "Deleted items pending purge. Access may be limited."),
    ]
    return rows


def j_safe(*parts: str) -> str:
    """os.path.join that yields '' if the first part is empty (no anchor)."""
    if not parts or not parts[0]:
        return ""
    return os.path.join(*parts)

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
