# -*- coding: utf-8 -*-
"""
GP-180 Studio -- Module MIDI sortie via WinMM (Windows natif).
Zero dependance externe. Fallback no-op sur macOS/Linux.

Usage :
    from gp180_midi import MidiOut, list_output_devices, slot_to_pc

    devs = list_output_devices()          # [(index, nom), ...]
    pc   = slot_to_pc(10, 'A')           # -> 27
    with MidiOut(devs[0][0]) as midi:
        midi.send_pc(pc)                 # GP-180 charge le preset
"""

import sys
import ctypes
import ctypes.wintypes

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    _winmm = ctypes.windll.winmm

    class _MIDIOUTCAPS(ctypes.Structure):
        _fields_ = [
            ("wMid",           ctypes.c_ushort),
            ("wPid",           ctypes.c_ushort),
            ("vDriverVersion", ctypes.c_uint),
            ("szPname",        ctypes.c_wchar * 32),
            ("wTechnology",    ctypes.c_ushort),
            ("wVoices",        ctypes.c_ushort),
            ("wNotes",         ctypes.c_ushort),
            ("wChannelMask",   ctypes.c_ushort),
            ("dwSupport",      ctypes.c_ulong),
        ]

# ── utilitaires publics ───────────────────────────────────────────────────────

def list_output_devices():
    """Retourne [(index, nom)] des sorties MIDI disponibles."""
    if not _IS_WIN:
        return []
    num  = _winmm.midiOutGetNumDevs()
    caps = _MIDIOUTCAPS()
    out  = []
    for i in range(num):
        _winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
        out.append((i, caps.szPname))
    return out


def slot_to_pc(slot_num: int, letter: str) -> int:
    """
    Convertit un slot GP-180 en numero Program Change.

    slot_num : 1-50
    letter   : 'A', 'B', 'C' ou 'D'
    retourne : PC 0-199

    Exemples :
        slot_to_pc(1,  'A') -> 0
        slot_to_pc(1,  'B') -> 1
        slot_to_pc(10, 'A') -> 36
        slot_to_pc(43, 'A') -> 168
        slot_to_pc(50, 'D') -> 199
    """
    return (slot_num - 1) * 4 + "ABCD".index(letter.upper())


def pc_to_slot(pc: int):
    """
    Convertit un Program Change en slot GP-180.
    retourne : (slot_num, letter)  ex: (32, 'C')
    """
    return pc // 4 + 1, "ABCD"[pc % 4]


# ── classe principale ─────────────────────────────────────────────────────────

class MidiOut:
    """
    Sortie MIDI WinMM -- utilisable comme context manager.

        with MidiOut(device_idx) as midi:
            if midi.ok:
                midi.send_pc(27)      # preset 10-A

    Sur macOS/Linux : no-op, midi.ok == False.
    """

    def __init__(self, device_idx: int):
        self._handle = ctypes.wintypes.HANDLE() if _IS_WIN else None
        self._ok     = False
        if not _IS_WIN:
            return
        ret      = _winmm.midiOutOpen(ctypes.byref(self._handle), device_idx, 0, 0, 0)
        self._ok = (ret == 0)

    @property
    def ok(self) -> bool:
        return self._ok

    def send_pc(self, program: int, channel: int = 0) -> bool:
        """
        Envoie un Program Change.
        program : 0-127 (valeurs > 127 ignorees)
        channel : 0-15  (canal MIDI, 0 = canal 1)
        retourne True si succes.
        """
        if not self._ok or not _IS_WIN:
            return False
        program = max(0, min(127, int(program)))
        channel = max(0, min(15,  int(channel)))
        msg = (0xC0 | channel) | (program << 8)
        return _winmm.midiOutShortMsg(self._handle, msg) == 0

    def close(self):
        if self._ok and _IS_WIN:
            _winmm.midiOutClose(self._handle)
            self._ok = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── test standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    devs = list_output_devices()
    print("Sorties MIDI :")
    for i, n in devs:
        print(f"  [{i}] {n}")
    if not devs:
        print("Aucun port MIDI.")
    else:
        idx = int(input("Port [0] : ").strip() or "0")
        with MidiOut(idx) as m:
            for pc in range(6):
                sn, sl = pc_to_slot(pc)
                m.send_pc(pc)
                print(f"  PC {pc} → slot {sn:02d}-{sl}")
                time.sleep(1.5)
