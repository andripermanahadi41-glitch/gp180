# -*- coding: utf-8 -*-
"""gp180_device -- konstanta perangkat Valeton GP-180 dan pengaman protokol.

STATUS: WORK IN PROGRESS.
Format .prst, protokol SysEx, VID/PID dan ID model di proyek ini MASIH milik
GP-200 (11 modul, 1224 byte, 128 preset). Semua itu BELUM diverifikasi untuk
GP-180. Selama PROTOCOL_VERIFIED = False, pengiriman SysEx ke pedal diblokir
supaya data GP-200 tidak tertulis ke GP-180 secara tidak sengaja.

Spesifikasi GP-180 (dari lembar produk resmi/toko, bukan dari protokol):
"""
import os

# --- spesifikasi publik GP-180 -------------------------------------------
MAX_MODULES       = 12     # modul bersamaan di rantai (GP-200 format lama: 11)
PRESET_SLOTS      = 200    # slot preset (100 pabrik)
FACTORY_PRESETS   = 100
SNAPTONE_FACTORY  = 50     # SnapTone/NAM bawaan (terverifikasi di firmware V1.0.0)
SNAPTONE_TOTAL    = 100
IR_USER_SLOTS     = 20
LOOPER_SECONDS    = 180
DRUM_PATTERNS     = 100    # "lebih dari 100"
SAMPLE_RATE       = 48000

# --- pengaman protokol ----------------------------------------------------
PROTOCOL_VERIFIED = False  # ubah ke True HANYA setelah capture USB GP-180 cocok
ENV_OVERRIDE      = "GP180_ALLOW_UNVERIFIED"


def protocol_allowed() -> bool:
    return PROTOCOL_VERIFIED or os.environ.get(ENV_OVERRIDE) == "1"


def require_verified():
    if not protocol_allowed():
        raise RuntimeError(
            "Protokol GP-180 belum diverifikasi: pengiriman SysEx diblokir. "
            "Lihat GP180_PORTING_NOTES.md. (Untuk uji sendiri dengan risiko "
            "sendiri: set %s=1.)" % ENV_OVERRIDE)
