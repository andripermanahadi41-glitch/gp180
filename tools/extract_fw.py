#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrait ce qui est lisible en clair dans un firmware GP-180 (.bin).

Usage:  python tools/extract_fw.py "GP-180 Firmware V1.0.0.bin" data/gp180_fw

Sorties
  snaptone_factory.json  None + 50 SnapTone d'usine + 50 slots vides  (FIABLE)
  models_draft.json      brouillon modeles/parametres          (A VERIFIER)
  usb_strings.json       chaines USB/BLE/MIDI du firmware
Structure decouverte (V1.0.0) :
  * table SnapTone : enregistrements de 40 octets = nom[32] + 5A id id 00 idx 00 00 0F
  * descripteur modele : en-tete 24 o (..., ff ff ff ff, ?, 00, n, 00, 4c 00 00 00, ..)
    puis n parametres de 20 o (min,max,step,def : float32 ; slot,ui,unit,type : u8)
    separes par 4 o, puis pool de chaines.  Le pool n'est pas homogene : la
    categorie et l'ordre des noms de parametres restent a confirmer.
"""
import json, math, os, re, struct, sys

def snaptone(fw):
    def rec(o):
        n = fw[o:o+32]; z = n.find(b"\0")
        if z <= 0 or not all(32 <= c < 127 for c in n[:z]) or any(n[z:]): return None
        return n[:z].decode(), fw[o+32:o+40]
    best = []
    o = 0
    while o < len(fw) - 40:
        r = rec(o)
        if r and r[1][0] == 0x5a and r[1][7] == 0x0f:
            run = [o]
            while rec(run[-1] + 40): run.append(run[-1] + 40)
            if len(run) >= 20:
                best.append(run); o = run[-1] + 40; continue
        o += 4
    if not best: return {}
    run = best[0]; items = []
    for i, p in enumerate(run):
        name, tail = rec(p)
        items.append({"index": i, "name": name, "kind": "none" if name == "None" else ("user_slot" if name.startswith("Empty") else "factory"),
                      "id": tail[1], "tail_hex": tail.hex()})
    return {"offset": run[0], "count": len(items), "copies_found": len(best), "items": items}

def cstr(fw, o):
    e = fw.find(b"\0", o); s = fw[o:e]
    if e < 0 or not s or not all(32 <= c < 127 for c in s) or len(s) > 40: return None, o
    return s.decode(), e + 1

def models(fw):
    sig = re.compile(rb"\xff\xff\xff\xff(.)\x00(.)\x00\x4c\x00\x00\x00", re.S)
    out = []
    for m in sig.finditer(fw):
        n = m.group(2)[0]; p = m.start() - 8 + 24
        if not 0 < n <= 16: continue
        params = []; o = p; ok = True
        for i in range(n):
            mn, mx, st, df = struct.unpack_from("<4f", fw, o)
            if any(math.isnan(x) or abs(x) > 1e8 for x in (mn, mx, st, df)): ok = False; break
            sl, ui, un, ty = fw[o+16:o+20]
            params.append(dict(min=mn, max=mx, step=st, default=df, slot=sl,
                               ui_order=ui, unit_code=un, type_code=ty))
            o += 20 if i == n - 1 else 24
        if not ok: continue
        strs = []
        for _ in range(n + 2):
            s, o = cstr(fw, o)
            if s is None: ok = False; break
            strs.append(s)
        if not ok: continue
        for pp, nm in zip(params, reversed(strs[1:1+n])): pp["name"] = nm
        out.append(dict(confidence="low", fw_offset=p, header_flag=m.group(1)[0],
                        name=strs[0], label_guess=strs[-1], n_params=n, params=params))
    return out

def usb_strings(fw):
    keys = (b"GP-180", b"Valeton", b"RMT_MIDI", b"BLE", b"Audio")
    seen = []
    for s in re.findall(rb"[ -~]{6,60}", fw):
        if any(k in s for k in keys) and s.decode() not in seen: seen.append(s.decode())
    return seen[:200]

def is_packed(fw):
    """V1.0.0 (8,4 MB) est en clair ; V1.1.1 (5 MB) est compresse (LZ maison,
    ni LZ4/LZF/FastLZ/zlib/lzma) : la table SnapTone n'y est plus contigue."""
    return fw[:4] == b"HTFW" and not snaptone(fw)

if __name__ == "__main__":
    src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else "data/gp180_fw"
    fw = open(src, "rb").read(); os.makedirs(dst, exist_ok=True)
    if is_packed(fw):
        sys.exit("Firmware compresse (ex. V1.1.1) : non supporte. Utiliser V1.0.0 "
                 "(en clair) ou fournir l'editeur officiel. Voir GP180_PORTING_NOTES.md.")
    for name, data in (("snaptone_factory", snaptone(fw)), ("models_draft", models(fw)),
                       ("usb_strings", usb_strings(fw))):
        json.dump(data, open(os.path.join(dst, name + ".json"), "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        print(name, "->", len(data) if not isinstance(data, dict) else data.get("count"))
