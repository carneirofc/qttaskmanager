"""Shared helpers for the on-demand scanners (disk / registry / links).

Unlike data.py these modules run *in-process* on a QThreadPool worker, not in
the collection subprocess — the scans are on-demand, I/O-bound (the GIL is
released during syscalls), and the links scan needs Qt (QFileInfo) to resolve
.lnk targets. Keeping them out of the subprocess avoids pickling large result
lists and lets us cancel a running scan via a threading.Event.
"""
from __future__ import annotations

import os

# ── severity levels (drive row colour + recommendation text) ──────────────────
SEV_OK     = "ok"       # safe to clear / healthy
SEV_REVIEW = "review"   # review before acting
SEV_WARN   = "warn"     # likely problem
SEV_BROKEN = "broken"   # confirmed broken / missing target
SEV_INFO   = "info"

# Host launchers that legitimately appear *without* a full path in Run/command
# strings. Flagging these as "missing" would be a false positive every time.
HOST_LAUNCHERS = {
    "rundll32.exe", "regsvr32.exe", "msiexec.exe", "explorer.exe",
    "control.exe", "dllhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "mshta.exe", "wscript.exe", "cscript.exe", "svchost.exe", "conhost.exe",
    "schtasks.exe", "net.exe", "sc.exe",
}


def human_size(n: int) -> str:
    """Bytes → compact human string (e.g. '1.4 GB')."""
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{int(f)} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} PB"


def expand(s: str) -> str:
    """Expand %VAR% style environment references; ctypes fallback if any remain."""
    if not s:
        return s
    out = os.path.expandvars(s)
    if "%" in out:
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(32767)
            if ctypes.windll.kernel32.ExpandEnvironmentStringsW(s, buf, 32767):
                out = buf.value
        except Exception:
            pass
    return out


def extract_exe(command: str) -> str:
    """Pull the executable token out of a command line.

    Handles: quoted-with-args  ("C:\\app.exe" --flag)  → between the quotes;
             unquoted-with-args (C:\\app.exe /run)      → prefix through .exe;
             bare token         (rundll32.exe)          → first token.
    """
    command = (command or "").strip()
    if not command:
        return ""
    if command[0] == '"':
        end = command.find('"', 1)
        return command[1:end] if end > 0 else command[1:]
    # Unquoted: take the ".exe" that *terminates* the executable — one followed
    # by whitespace or end-of-string — so ".exe" inside a directory name
    # (C:\foo.exe.bak\app.exe /run) doesn't truncate the path mid-way.
    low = command.lower()
    start = 0
    while True:
        idx = low.find(".exe", start)
        if idx < 0:
            break
        after = idx + 4
        if after >= len(command) or command[after] in " \t":
            return command[:after]
        start = after
    return command.split()[0]


def is_store_or_virtual(path: str) -> bool:
    """True for UWP/Store, MSI-advertised or shell/CLSID targets we must not flag."""
    low = (path or "").lower()
    return (
        not low
        or "\\windowsapps\\" in low
        or "shell:appsfolder" in low
        or low.startswith("@{")
        or "::{" in low
    )


def is_host_launcher(exe: str) -> bool:
    """True for a bare system launcher referenced without a directory."""
    if not exe:
        return False
    return (not os.path.isabs(exe)) and os.path.basename(exe).lower() in HOST_LAUNCHERS


def path_missing(path: str) -> bool:
    """True only when we are confident the path does not exist.

    Access errors return False (treated as 'unknown, do not flag') so a denied
    directory is never reported as a broken target.
    """
    if not path:
        return False
    try:
        return not os.path.exists(path)
    except OSError:
        return False


def dir_size(path: str, cancel, progress=None) -> tuple[int, int, int]:
    """Recursive (bytes, files, skipped) for a directory tree.

    Iterative os.scandir DFS — does not follow symlinks/junctions (avoids cycles
    and double counting), polls the cancel Event, and tallies every access error
    as 'skipped' instead of aborting.
    """
    total = files = skipped = 0
    stack = [path]
    while stack:
        if cancel.is_set():
            break
        current = stack.pop()
        try:
            it = os.scandir(current)
        except OSError:
            skipped += 1
            continue
        with it:
            for entry in it:
                if cancel.is_set():
                    break
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # is_dir(follow_symlinks=False) skips symlinks but NOT
                        # NTFS junctions — skip those too to avoid cycles and
                        # double-counting a tree that's reparse-pointed elsewhere.
                        if entry.is_junction():
                            continue
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        files += 1
                except OSError:
                    skipped += 1
    return total, files, skipped
