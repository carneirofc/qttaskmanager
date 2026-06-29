"""Behavioural threat heuristics — flag running processes that look like they
may be performing attacks, data theft, persistence or coin-mining.

READ-ONLY: this only *observes* processes (psutil), the registry (winreg) and
the filesystem (os/QFileInfo). It never kills, modifies or deletes anything.

How it works
------------
Each process is scored against a weighted rule set spanning four signal classes:

  • process metadata — suspicious launch directory, name masquerading as a
    system binary, look-alike / double-extension names, unsigned binaries
    outside trusted locations, freshly-written executables;
  • command line     — encoded/hidden PowerShell, download cradles
    (certutil / bitsadmin / mshta http / IEX DownloadString), LOLBin abuse,
    shadow-copy deletion, miner pool strings;
  • network          — connections to known C2 / backdoor ports, listeners
    served from a user-writable directory;
  • resource + persistence — sustained high CPU, and an autostart entry
    (Run key / Startup folder) pointing at the binary.

Every rule contributes points to a 0-100 risk score *and* records a one-line
finding. Weights are tuned so a single weak signal stays below the listing
floor (a benign unsigned dev tool won't show up), while combinations
(unsigned + temp path + odd port) escalate to High/Critical. A process is only
reported when it trips enough to clear `_LISTING_FLOOR`.
"""
from __future__ import annotations

import ipaddress
import os
import time
import winreg
from collections import defaultdict
from collections.abc import Callable
from threading import Event

import psutil

from .scan_data import SEV_INFO, SEV_REVIEW, SEV_WARN, SEV_BROKEN, extract_exe, expand
from . import winsig

# ── scoring ──────────────────────────────────────────────────────────────────
_LISTING_FLOOR = 15      # processes scoring below this are not reported
_SCORE_CAP = 100

# score → (severity, human risk label); checked high-to-low
_BANDS: list[tuple[int, str, str]] = [
    (60, SEV_BROKEN, "Critical"),
    (35, SEV_WARN,   "High"),
    (20, SEV_REVIEW, "Medium"),
    (0,  SEV_INFO,   "Low"),
]

# ── reference data ───────────────────────────────────────────────────────────

# System binaries whose name is routinely impersonated; value is the directory
# the genuine binary must live in (matched case-insensitively).
def _system_homes() -> dict[str, str]:
    windir = (os.environ.get("SystemRoot") or r"C:\Windows").lower()
    system32 = os.path.join(windir, "system32")
    return {
        "svchost.exe":  system32,
        "csrss.exe":    system32,
        "lsass.exe":    system32,
        "services.exe": system32,
        "winlogon.exe": system32,
        "wininit.exe":  system32,
        "smss.exe":     system32,
        "spoolsv.exe":  system32,
        "taskhostw.exe": system32,
        "dwm.exe":      system32,
        "conhost.exe":  system32,
        "explorer.exe": windir,
    }

# Ports commonly used by backdoors / C2 / RATs (not exhaustive — high-signal set).
_SUSPICIOUS_PORTS: dict[int, str] = {
    4444: "Metasploit default", 4445: "Metasploit", 5554: "worm/backdoor",
    1337: "elite/backdoor", 31337: "Back Orifice", 12345: "NetBus",
    12346: "NetBus", 6666: "IRC botnet", 6667: "IRC C2", 6668: "IRC C2",
    6669: "IRC C2", 9001: "Tor", 9050: "Tor SOCKS", 1080: "SOCKS proxy",
    5555: "ADB/backdoor", 8087: "C2", 2222: "alt-SSH/backdoor",
}

# Command-line indicators: (needle, weight, finding). All matched lower-cased on
# the full command line; some require two needles (handled inline below).
_CMD_SINGLE: list[tuple[str, int, str]] = [
    ("-encodedcommand", 30, "Encoded PowerShell command (-EncodedCommand)"),
    ("frombase64string", 22, "Base64-decoded payload in command line"),
    ("downloadstring",   28, "PowerShell download cradle (DownloadString)"),
    ("downloadfile",     24, "Remote file download in command line"),
    ("invoke-webrequest", 18, "Remote fetch via Invoke-WebRequest"),
    ("invoke-expression", 22, "Dynamic code execution (Invoke-Expression)"),
    ("iex(",             22, "Dynamic code execution (IEX)"),
    ("-windowstyle hidden", 18, "Runs with a hidden window"),
    ("-w hidden",        18, "Runs with a hidden window"),
    ("stratum+tcp",      35, "Cryptominer pool address (stratum+tcp)"),
    ("--donate-level",   35, "Cryptominer flag (--donate-level)"),
    ("xmrig",            35, "Known cryptominer (xmrig)"),
    ("nanopool",         30, "Cryptominer pool (nanopool)"),
]


def _is_external(ip: str) -> bool:
    """True for a routable public address (not private/loopback/link-local)."""
    if not ip:
        return False
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local
                or a.is_multicast or a.is_reserved or a.is_unspecified)


# ── trusted-location / signature helpers ─────────────────────────────────────

def _trusted_dirs() -> list[str]:
    env = os.environ.get
    dirs = [
        env("SystemRoot", r"C:\Windows"),
        env("ProgramFiles", r"C:\Program Files"),
        env("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    return [os.path.normcase(os.path.normpath(d)) + os.sep for d in dirs if d]


def _suspicious_dirs() -> list[str]:
    env = os.environ.get
    j = os.path.join
    local = env("LOCALAPPDATA", "")
    roaming = env("APPDATA", "")
    userprofile = env("USERPROFILE", "")
    windir = env("SystemRoot", r"C:\Windows")
    dirs = [
        env("TEMP", ""),
        j(windir, "Temp"),
        j(local, "Temp") if local else "",
        j(userprofile, "Downloads") if userprofile else "",
        j(userprofile, "AppData", "Local", "Temp") if userprofile else "",
        r"C:\$Recycle.Bin",
        j(env("PUBLIC", r"C:\Users\Public"), ""),
    ]
    return [os.path.normcase(os.path.normpath(d)) + os.sep for d in dirs if d]


def _under(path: str, dirs: list[str]) -> bool:
    if not path:
        return False
    norm = os.path.normcase(os.path.normpath(path))
    return any(norm.startswith(d) for d in dirs)


def _classify_signature(exe: str, trusted: list[str]) -> tuple[str, bool]:
    """Return (label, is_suspicious) for the binary's signature state."""
    if not exe:
        return ("unknown", False)
    in_trusted = _under(exe, trusted)
    sig = winsig.verify_embedded(exe)
    if sig is True:
        return ("signed", False)
    if in_trusted:
        # Catalog-signed in-box binaries report as unsigned here — trust the path.
        return ("trusted-dir", False)
    if sig is False:
        return ("unsigned", True)
    return ("unknown", False)


# ── autostart persistence ────────────────────────────────────────────────────

_RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run"),
]


def _collect_autoruns() -> set[str]:
    """Normalised exe paths referenced by Run keys and the Startup folders."""
    found: set[str] = set()

    for hive, sub in _RUN_KEYS:
        try:
            key = winreg.OpenKey(hive, sub)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    _name, value, _typ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                exe = extract_exe(expand(str(value)))
                if exe:
                    found.add(os.path.normcase(os.path.normpath(exe)))

    # Startup folders — resolve .lnk targets via Qt (available on the worker thread).
    try:
        from PySide6.QtCore import QFileInfo
        env = os.environ.get
        startups = [
            os.path.join(env("APPDATA", ""), "Microsoft", "Windows",
                         "Start Menu", "Programs", "Startup"),
            os.path.join(env("ProgramData", r"C:\ProgramData"), "Microsoft",
                         "Windows", "Start Menu", "Programs", "Startup"),
        ]
        for folder in startups:
            if not folder or not os.path.isdir(folder):
                continue
            for entry in os.scandir(folder):
                target = entry.path
                if entry.name.lower().endswith(".lnk"):
                    link = QFileInfo(entry.path).symLinkTarget()
                    if link:
                        target = link
                if target:
                    found.add(os.path.normcase(os.path.normpath(target)))
    except Exception:
        pass

    return found


def _connections_by_pid() -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    try:
        for c in psutil.net_connections(kind="inet"):
            out[c.pid or 0].append(c)
    except (psutil.AccessDenied, OSError):
        pass
    return out


# ── per-process evaluation ───────────────────────────────────────────────────

def _looks_like_lookalike(name: str, homes: dict[str, str]) -> str | None:
    """Detect digit-for-letter masquerades of system names (svch0st, scvhost)."""
    low = name.lower()
    if low in homes:
        return None
    # double extension e.g. invoice.pdf.exe
    base = low[:-4] if low.endswith(".exe") else low
    if "." in base and not base.endswith((".", "")):
        parts = base.split(".")
        if len(parts) >= 2 and parts[-1] in (
            "pdf", "doc", "docx", "xls", "xlsx", "jpg", "png", "txt", "zip", "scr"
        ):
            return "Double extension — looks like a document but is an executable"
    # digit-substituted system name (svch0st.exe ~ svchost.exe)
    translated = low.translate(str.maketrans("013457", "oieast"))
    if translated in homes and translated != low:
        return f"Name mimics a system process ({translated}) via character swap"
    return None


def _evaluate(ctx: dict, homes: dict[str, str], autoruns: set[str],
              trusted: list[str], suspicious: list[str]) -> tuple[list[str], int]:
    hits: list[str] = []
    score = 0

    def add(weight: int, finding: str) -> None:
        nonlocal score
        score += weight
        hits.append(finding)

    name = ctx["name"]
    exe = ctx["exe"]
    cmd_low = ctx["cmdline"].lower()

    # ── process metadata ──────────────────────────────────────────────────────
    if exe and _under(exe, suspicious):
        add(22, f"Runs from a user-writable / temp location: {os.path.dirname(exe)}")

    home = homes.get(name.lower())
    if home and exe and os.path.normcase(os.path.dirname(exe)) != os.path.normcase(home):
        add(35, f"Impersonates system process '{name}' from {os.path.dirname(exe)} "
                f"(expected {home})")

    look = _looks_like_lookalike(name, homes)
    if look:
        add(18, look)

    sig_label, sig_bad = ctx["sig_label"], ctx["sig_bad"]
    if sig_bad:
        add(12, "Unsigned executable outside trusted system locations")

    if exe and not _under(exe, trusted):
        try:
            age = time.time() - os.path.getmtime(exe)
            if 0 <= age < 86400:
                add(10, "Executable was created/modified within the last 24 hours")
        except OSError:
            pass

    # ── command line ──────────────────────────────────────────────────────────
    for needle, weight, finding in _CMD_SINGLE:
        if needle in cmd_low:
            add(weight, finding)

    if "powershell" in cmd_low and (" -enc " in cmd_low or cmd_low.endswith(" -enc")
                                    or " -e " in cmd_low):
        add(30, "Encoded PowerShell command (-enc)")
    if "powershell" in cmd_low and "-nop" in cmd_low and "hidden" in cmd_low:
        add(15, "PowerShell run with -NoProfile and hidden window")
    if "certutil" in cmd_low and ("-urlcache" in cmd_low or "-decode" in cmd_low):
        add(28, "certutil used to download/decode payload")
    if "bitsadmin" in cmd_low and "/transfer" in cmd_low:
        add(28, "bitsadmin used to transfer a remote file")
    if "mshta" in cmd_low and ("http" in cmd_low or "javascript:" in cmd_low
                               or "vbscript:" in cmd_low):
        add(25, "mshta executing remote/script content")
    if "regsvr32" in cmd_low and ("scrobj" in cmd_low or "http" in cmd_low or "/i:" in cmd_low):
        add(25, "regsvr32 LOLBin abuse (scriptlet / remote)")
    if "rundll32" in cmd_low and "javascript:" in cmd_low:
        add(25, "rundll32 executing JavaScript")
    if "vssadmin" in cmd_low and "delete" in cmd_low and "shadow" in cmd_low:
        add(40, "Deletes Volume Shadow Copies (ransomware behaviour)")
    if "wbadmin" in cmd_low and "delete" in cmd_low:
        add(35, "Deletes backups (wbadmin delete)")
    if "schtasks" in cmd_low and "/create" in cmd_low:
        add(15, "Creates a scheduled task (possible persistence)")
    if "net" in cmd_low and "user" in cmd_low and "/add" in cmd_low:
        add(20, "Creates a local user account (net user /add)")

    # ── network ───────────────────────────────────────────────────────────────
    ext = ctx["ext_count"]
    for port, label in ctx["sus_ports"]:
        add(22, f"Connection on suspicious port {port} ({label})")
    if ctx["listening"] and exe and _under(exe, suspicious):
        add(18, "Listening for inbound connections from a temp/user location")

    # ── resource + persistence ────────────────────────────────────────────────
    if ctx["cpu"] >= 85.0:
        add(12, f"Sustained high CPU ({ctx['cpu']:.0f}%) — possible cryptominer")

    if exe and os.path.normcase(os.path.normpath(exe)) in autoruns:
        add(12, "Has an autostart entry (Run key / Startup folder)")

    _ = (sig_label, ext)  # referenced for clarity; not all paths score
    return hits, min(score, _SCORE_CAP)


def _band(score: int) -> tuple[str, str]:
    for threshold, sev, label in _BANDS:
        if score >= threshold:
            return sev, label
    return SEV_INFO, "Low"


def _sleep_cancellable(seconds: float, cancel: Event) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if cancel.is_set():
            return
        time.sleep(0.05)


def scan_threats(cancel: Event, progress: Callable[[str], None]) -> list[dict]:
    homes = _system_homes()
    trusted = _trusted_dirs()
    suspicious = _suspicious_dirs()

    progress("Collecting autostart entries…")
    autoruns = _collect_autoruns()

    progress("Mapping network connections…")
    conns = _connections_by_pid()

    progress("Sampling CPU usage…")
    procs = []
    for p in psutil.process_iter():
        if cancel.is_set():
            return []
        procs.append(p)
        try:
            p.cpu_percent(None)   # prime the per-process delta
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _sleep_cancellable(0.6, cancel)

    rows: list[dict] = []
    total = len(procs) or 1
    ncpu = psutil.cpu_count() or 1
    for i, p in enumerate(procs):
        if cancel.is_set():
            break
        if i % 25 == 0:
            progress(f"Analysing processes… {i}/{total}")

        try:
            with p.oneshot():
                pid = p.pid
                name = p.name()
                try:
                    exe = p.exe() or ""
                except (psutil.AccessDenied, FileNotFoundError, OSError):
                    exe = ""
                try:
                    cmdline = " ".join(p.cmdline())
                except (psutil.AccessDenied, OSError):
                    cmdline = ""
                try:
                    user = p.username()
                except (psutil.AccessDenied, OSError):
                    user = ""
                # cpu_percent is reported per-core-sum; normalise to overall %.
                cpu = (p.cpu_percent(None) or 0.0) / ncpu
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        # network features for this pid
        sus_ports: list[tuple[int, str]] = []
        ext_count = 0
        listening = False
        seen_ports: set[int] = set()
        for c in conns.get(pid, ()):
            status = getattr(c, "status", "") or ""
            if status == psutil.CONN_LISTEN:
                listening = True
            r = getattr(c, "raddr", None)
            if r:
                if _is_external(r.ip):
                    ext_count += 1
                if r.port in _SUSPICIOUS_PORTS and r.port not in seen_ports:
                    sus_ports.append((r.port, _SUSPICIOUS_PORTS[r.port]))
                    seen_ports.add(r.port)
            l = getattr(c, "laddr", None)
            if status == psutil.CONN_LISTEN and l and l.port in _SUSPICIOUS_PORTS \
                    and l.port not in seen_ports:
                sus_ports.append((l.port, _SUSPICIOUS_PORTS[l.port]))
                seen_ports.add(l.port)

        sig_label, sig_bad = _classify_signature(exe, trusted)

        ctx = {
            "pid": pid, "name": name, "exe": exe, "cmdline": cmdline, "user": user,
            "cpu": cpu, "sig_label": sig_label, "sig_bad": sig_bad,
            "ext_count": ext_count, "sus_ports": sus_ports, "listening": listening,
        }
        hits, score = _evaluate(ctx, homes, autoruns, trusted, suspicious)
        if score < _LISTING_FLOOR:
            continue

        sev, risk = _band(score)
        net = []
        if ext_count:
            net.append(f"{ext_count} ext")
        if sus_ports:
            net.append("⚠ " + ",".join(str(pt) for pt, _ in sus_ports))
        if listening:
            net.append("listen")

        rows.append({
            "pid":        pid,
            "name":       name,
            "risk":       risk,
            "score":      str(score),
            "score_num":  score,
            "signature":  sig_label,
            "network":    " · ".join(net) or "—",
            "findings":   "; ".join(hits),
            "exe":        exe or "(unknown)",
            "user":       user,
            "severity":   sev,
        })

    rows.sort(key=lambda r: r["score_num"], reverse=True)
    return rows
