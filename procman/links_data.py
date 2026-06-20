"""Broken application-link scan (READ-ONLY).

Walks the Start Menu (user + machine) and Desktop (user + public) for .lnk
shortcuts and reports those whose target executable no longer exists. Shortcut
targets are resolved with QFileInfo — running in-process (not the subprocess)
is what makes Qt available here.

False-positive guards: shortcuts that resolve to an empty target (Control
Panel / Recycle Bin / This PC and other shell/CLSID items) and Store/virtual
targets are skipped — only a confidently-missing concrete path is flagged.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QFileInfo

from .scan_data import is_store_or_virtual, SEV_BROKEN


def _sources() -> list[tuple[str, str]]:
    env = os.environ.get
    appdata     = env("APPDATA", "")
    programdata = env("ProgramData", r"C:\ProgramData")
    userprofile = env("USERPROFILE", "")
    public      = env("PUBLIC", r"C:\Users\Public")

    j = os.path.join
    return [
        ("Start Menu (user)",    j(appdata, "Microsoft", "Windows", "Start Menu", "Programs")),
        ("Start Menu (machine)", j(programdata, "Microsoft", "Windows", "Start Menu", "Programs")),
        ("Desktop (user)",       j(userprofile, "Desktop")),
        ("Desktop (public)",     j(public, "Desktop")),
    ]


def _iter_lnks(root: str, cancel: Event):
    """Yield every *.lnk path under root, skipping inaccessible directories."""
    stack = [root]
    while stack:
        if cancel.is_set():
            return
        current = stack.pop()
        try:
            it = os.scandir(current)
        except OSError:
            continue
        with it:
            for entry in it:
                if cancel.is_set():
                    return
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.is_junction():   # don't follow reparse points
                            continue
                        stack.append(entry.path)
                    elif entry.name.lower().endswith(".lnk"):
                        yield entry.path
                except OSError:
                    continue


def scan_broken_links(cancel: Event, progress: Callable[[str], None]) -> list[dict]:
    rows: list[dict] = []
    for source, root in _sources():
        if cancel.is_set():
            break
        if not root or not os.path.isdir(root):
            continue
        progress(f"Scanning: {source}…")

        for lnk in _iter_lnks(root, cancel):
            target = QFileInfo(lnk).symLinkTarget()
            # Empty target → shell/CLSID/advertised shortcut; not resolvable to a
            # file, so we must not flag it as broken.
            if not target or is_store_or_virtual(target):
                continue
            # A relative target is relative to the .lnk's folder, not the cwd.
            resolved = (target if os.path.isabs(target)
                        else os.path.normpath(os.path.join(os.path.dirname(lnk), target)))
            if QFileInfo(resolved).exists():
                continue
            rows.append({
                "name":     os.path.splitext(os.path.basename(lnk))[0],
                "source":   source,
                "target":   resolved,
                "link":     lnk,
                "status":   "Target missing",
                "severity": SEV_BROKEN,
            })
    return rows
