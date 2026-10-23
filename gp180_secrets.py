# -*- coding: utf-8 -*-
"""Chiffrement des cles API, lie a la session Windows (DPAPI).

Objectif : que les cles ne soient pas en clair dans config.json. Copier le
fichier sur un autre PC ou l'ouvrir depuis un autre compte Windows le rend
illisible -- c'est CryptProtectData/CryptUnprotectData (DPAPI) avec la portee
utilisateur courant.

Format stocke : "dpapi:" + base64(blob chiffre). Un prefixe explicite permet de
reconnaitre une valeur chiffree d'une valeur en clair (retrocompatibilite : une
ancienne cle en clair reste lue telle quelle, puis re-chiffree au prochain
enregistrement).

Hors Windows (dev/CI Linux, Mac), DPAPI n'existe pas : on retombe sur un
encodage reversible marque "plain:" -- AUCUNE protection, mais l'appli reste
fonctionnelle. Le vrai deploiement etant Windows, c'est acceptable ; le prefixe
distinct evite de faire croire a tort que la donnee est protegee.
"""
import base64
import sys

_PREFIX_DPAPI = "dpapi:"
_PREFIX_PLAIN = "plain:"


def _win_dpapi_available():
    return sys.platform == "win32"


def _dpapi_encrypt(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob_in(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    blob_out = DATA_BLOB()
    src = blob_in(data)
    # CRYPTPROTECT_UI_FORBIDDEN = 0x1 : jamais d'UI
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob_in(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    blob_out = DATA_BLOB()
    src = blob_in(data)
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def encrypt_key(plaintext: str) -> str:
    """Chiffre une cle pour stockage dans config.json."""
    if not plaintext:
        return ""
    raw = plaintext.encode("utf-8")
    if _win_dpapi_available():
        try:
            blob = _dpapi_encrypt(raw)
            return _PREFIX_DPAPI + base64.b64encode(blob).decode("ascii")
        except Exception:
            pass  # retombe sur plain si DPAPI echoue
    return _PREFIX_PLAIN + base64.b64encode(raw).decode("ascii")


def decrypt_key(stored: str) -> str:
    """Dechiffre une cle lue depuis config.json. Tolere les cles en clair
    (anciennes configs) : renvoyees telles quelles."""
    if not stored:
        return ""
    if stored.startswith(_PREFIX_DPAPI):
        b64 = stored[len(_PREFIX_DPAPI):]
        try:
            return _dpapi_decrypt(base64.b64decode(b64)).decode("utf-8")
        except Exception:
            return ""      # cle chiffree sur un autre compte/PC : illisible ici
    if stored.startswith(_PREFIX_PLAIN):
        try:
            return base64.b64decode(stored[len(_PREFIX_PLAIN):]).decode("utf-8")
        except Exception:
            return ""
    # ni l'un ni l'autre : ancienne cle en clair, retrocompatibilite
    return stored


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith((_PREFIX_DPAPI, _PREFIX_PLAIN))
