"""Shared read-only winreg helpers for the registry features."""
from __future__ import annotations

import winreg

HIVE_LABEL = {
    winreg.HKEY_CLASSES_ROOT:  "HKCR",
    winreg.HKEY_CURRENT_USER:  "HKCU",
    winreg.HKEY_LOCAL_MACHINE: "HKLM",
    winreg.HKEY_USERS:         "HKU",
}

_TYPE_NAME = {
    winreg.REG_SZ:        "REG_SZ",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_BINARY:    "REG_BINARY",
    winreg.REG_DWORD:     "REG_DWORD",
    winreg.REG_QWORD:     "REG_QWORD",
    winreg.REG_MULTI_SZ:  "REG_MULTI_SZ",
    winreg.REG_NONE:      "REG_NONE",
}


def type_name(t: int) -> str:
    return _TYPE_NAME.get(t, f"type {t}")


def open_key(root, subkey: str, view: int = 0):
    return winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view)


def subkeys(root, subkey: str, view: int = 0) -> list[str]:
    out: list[str] = []
    try:
        k = open_key(root, subkey, view)
    except OSError:
        return out
    with k:
        i = 0
        while True:
            try:
                out.append(winreg.EnumKey(k, i))
            except OSError:
                break
            i += 1
    return out


def values(root, subkey: str, view: int = 0) -> list[tuple]:
    out: list[tuple] = []
    try:
        k = open_key(root, subkey, view)
    except OSError:
        return out
    with k:
        i = 0
        while True:
            try:
                out.append(winreg.EnumValue(k, i))  # (name, data, type)
            except OSError:
                break
            i += 1
    return out


def has_subkeys(root, subkey: str, view: int = 0) -> bool:
    try:
        k = open_key(root, subkey, view)
    except OSError:
        return False
    with k:
        try:
            return winreg.QueryInfoKey(k)[0] > 0   # [0] = number of subkeys
        except OSError:
            return False


def format_value(data, typ: int) -> str:
    if typ == winreg.REG_BINARY and isinstance(data, (bytes, bytearray)):
        head = bytes(data[:48])
        return head.hex(" ") + (" …" if len(data) > 48 else "")
    if typ == winreg.REG_MULTI_SZ and isinstance(data, (list, tuple)):
        return "  |  ".join(str(x) for x in data)
    return "" if data is None else str(data)
