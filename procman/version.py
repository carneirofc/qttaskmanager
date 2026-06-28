"""Application version and build provenance.

The version, the commit the build was cut from, and the build date are baked
into ``_build_info.py`` at build time (see build.ps1). When running from a dev
checkout that file is absent, so we fall back to ``git`` and the installed
package metadata.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

UNKNOWN = "unknown"

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_info() -> dict[str, str]:
    """Metadata frozen in at build time, or an empty dict in a dev checkout."""
    try:
        from . import _build_info as info  # type: ignore[attr-defined]
    except Exception:
        return {}
    return {
        "version": getattr(info, "VERSION", "") or "",
        "commit": getattr(info, "COMMIT", "") or "",
        "date": getattr(info, "DATE", "") or "",
    }


def _git(*args: str) -> str:
    """Run a read-only git command in the repo, returning "" on any failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def version() -> str:
    baked = _build_info().get("version")
    if baked:
        return baked
    try:
        from importlib.metadata import version as _pkg_version

        return _pkg_version("qttaskmanager")
    except Exception:
        pass
    return _pyproject_version() or UNKNOWN


def _pyproject_version() -> str:
    """Read the version straight from pyproject.toml (dev checkout fallback)."""
    try:
        import tomllib

        with open(_REPO_ROOT / "pyproject.toml", "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    except Exception:
        return ""


def commit() -> str:
    baked = _build_info().get("commit")
    if baked:
        return baked
    return _git("rev-parse", "--short", "HEAD") or UNKNOWN


def build_date() -> str:
    baked = _build_info().get("date")
    if baked:
        return baked
    # Dev checkout: the timestamp of the HEAD commit (ISO with offset).
    return _git("show", "-s", "--format=%ci", "HEAD") or UNKNOWN
