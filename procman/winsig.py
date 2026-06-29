"""Authenticode signature verification via WinVerifyTrust (ctypes).

Used by the threat scanner to tell a properly-signed binary apart from an
unsigned one dropped into a user-writable directory. This checks the
*embedded* signature only — many in-box Windows binaries are catalog-signed
and will report as unsigned here, so callers must treat "unsigned but located
under a trusted system directory" as benign (see threat_data._classify_signature).

READ-ONLY: opens the file for hashing/verification, never modifies it. Results
are cached per absolute path for the lifetime of the process so re-scans are
cheap. Revocation checking is disabled so verification never touches the network.
"""
from __future__ import annotations

import os

try:
    import ctypes
    from ctypes import wintypes

    _wintrust = ctypes.WinDLL("wintrust")
    _WinVerifyTrust = _wintrust.WinVerifyTrust
    _WinVerifyTrust.restype = wintypes.LONG
    _AVAILABLE = True
except Exception:  # non-Windows, or wintrust unavailable
    _AVAILABLE = False


if _AVAILABLE:
    # WinVerifyTrust constants
    _WTD_UI_NONE = 2
    _WTD_REVOKE_NONE = 0
    _WTD_CHOICE_FILE = 1
    _WTD_STATEACTION_VERIFY = 1
    _WTD_STATEACTION_CLOSE = 2
    _WTD_SAFER_FLAG = 0x100

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class _WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pcwszFilePath", wintypes.LPCWSTR),
            ("hFile", wintypes.HANDLE),
            ("pgKnownSubject", ctypes.c_void_p),
        ]

    class _WINTRUST_DATA(ctypes.Structure):
        # The real struct has a union of pointers (file/catalog/blob/…); we only
        # ever use the file member and all pointers are the same width, so a plain
        # pointer field models it correctly here.
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pPolicyCallbackData", ctypes.c_void_p),
            ("pSIPClientData", ctypes.c_void_p),
            ("dwUIChoice", wintypes.DWORD),
            ("fdwRevocationChecks", wintypes.DWORD),
            ("dwUnionChoice", wintypes.DWORD),
            ("pFile", ctypes.POINTER(_WINTRUST_FILE_INFO)),
            ("dwStateAction", wintypes.DWORD),
            ("hWVTStateData", wintypes.HANDLE),
            ("pwszURLReference", wintypes.LPWSTR),
            ("dwProvFlags", wintypes.DWORD),
            ("dwUIContext", wintypes.DWORD),
            ("pSignatureSettings", ctypes.c_void_p),
        ]

    # WINTRUST_ACTION_GENERIC_VERIFY_V2
    _ACTION = _GUID(
        0x00AAC56B, 0xCD44, 0x11D0,
        (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
    )


_cache: dict[str, "bool | None"] = {}


def verify_embedded(path: str) -> "bool | None":
    """Return True (trusted), False (no/invalid embedded signature) or None (unknown).

    None means the check could not run (non-Windows, no file, access error) and the
    caller must not treat the binary as unsigned.
    """
    if not _AVAILABLE or not path:
        return None
    if path in _cache:
        return _cache[path]

    result: "bool | None"
    try:
        if not os.path.isfile(path):
            result = None
        else:
            file_info = _WINTRUST_FILE_INFO(
                cbStruct=ctypes.sizeof(_WINTRUST_FILE_INFO),
                pcwszFilePath=path,
                hFile=None,
                pgKnownSubject=None,
            )
            data = _WINTRUST_DATA(
                cbStruct=ctypes.sizeof(_WINTRUST_DATA),
                dwUIChoice=_WTD_UI_NONE,
                fdwRevocationChecks=_WTD_REVOKE_NONE,
                dwUnionChoice=_WTD_CHOICE_FILE,
                pFile=ctypes.pointer(file_info),
                dwStateAction=_WTD_STATEACTION_VERIFY,
                dwProvFlags=_WTD_SAFER_FLAG,
            )
            res = _WinVerifyTrust(0, ctypes.byref(_ACTION), ctypes.byref(data))
            # Free the state data WinVerifyTrust allocated during VERIFY.
            data.dwStateAction = _WTD_STATEACTION_CLOSE
            _WinVerifyTrust(0, ctypes.byref(_ACTION), ctypes.byref(data))
            result = (res == 0)
    except Exception:
        result = None

    _cache[path] = result
    return result
