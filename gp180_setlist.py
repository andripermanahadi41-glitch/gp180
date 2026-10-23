# -*- coding: utf-8 -*-
"""Harmonisation du volume d'une setlist de presets GP-180.

Chaque preset a un volume global (patch_vol, octet 0x38, plage 0-100) qui
determine le niveau de sortie. Le probleme en concert : un clean a patch_vol 85
et un high-gain a patch_vol 15 sont calibres pour sortir au meme volume percu,
mais si les presets viennent de sources differentes (generes a des moments
differents, telecharges, bidouilles a la main), les niveaux ne matchent pas.

Ce module :
  1. Decode chaque .prst
  2. Estime le patch_vol ideal via estimate_patch_vol (calibre sur mesures reelles)
  3. Permet a l'utilisateur d'ajuster chaque valeur via un slider
  4. Reecrit les .prst avec les nouveaux patch_vol (seul cet octet + checksum changent)
"""
import os
import struct

from gp180lib import decode_prst, Tables, checksum, FILE_SIZE
from gp180_agent import estimate_patch_vol, decoded_to_spec, OFF_PATCH_VOL


def analyze_setlist(paths, tables):
    """Analyse une liste de fichiers .prst et renvoie les infos de volume.

    Renvoie une liste de dicts :
      [{"path": ..., "name": ..., "current_pv": int, "suggested_pv": int,
        "amp_model": str, "amp_gain": float, "dst_on": bool}, ...]

    Leve ValueError si un fichier est illisible.
    """
    results = []
    for p in paths:
        d = decode_prst(p, tables)
        spec = decoded_to_spec(d)
        current_pv = d.get("patch_vol")
        if current_pv is None:
            # Lire directement depuis le binaire
            raw = open(p, "rb").read()
            current_pv = raw[OFF_PATCH_VOL]

        suggested_pv = estimate_patch_vol(spec)

        # Infos contextuelles pour l'affichage
        amp = spec["modules"].get("AMP") or {}
        dst = spec["modules"].get("DST") or {}
        amp_model = amp.get("model") or ""
        amp_gain = (amp.get("params") or {}).get("Gain", 0)
        dst_on = bool(dst.get("on") and dst.get("model"))

        results.append({
            "path": p,
            "name": spec.get("name") or os.path.splitext(os.path.basename(p))[0],
            "current_pv": int(current_pv),
            "suggested_pv": int(suggested_pv),
            "amp_model": amp_model,
            "amp_gain": float(amp_gain),
            "dst_on": dst_on,
        })
    return results


def apply_setlist(entries, output_dir, log=None):
    """Applique les patch_vol ajustes et ecrit les presets dans output_dir.

    entries : liste de dicts avec au minimum {"path": ..., "final_pv": int}
    output_dir : dossier de sortie (cree si necessaire)
    log : callback(str) optionnel

    Renvoie la liste des chemins ecrits.
    """
    os.makedirs(output_dir, exist_ok=True)
    written = []
    for e in entries:
        raw = bytearray(open(e["path"], "rb").read())
        if len(raw) != FILE_SIZE:
            raise ValueError("Taille inattendue pour %s : %d" % (e["path"], len(raw)))

        old_pv = raw[OFF_PATCH_VOL]
        new_pv = int(round(max(2, min(100, float(e["final_pv"])))))
        raw[OFF_PATCH_VOL] = new_pv

        # Recalculer le checksum
        cs = checksum(bytes(raw))
        struct.pack_into(">H", raw, FILE_SIZE - 2, cs)

        out_path = os.path.join(output_dir, os.path.basename(e["path"]))
        open(out_path, "wb").write(raw)
        written.append(out_path)

        delta = new_pv - old_pv
        sign = "+" if delta > 0 else ""
        msg = "  %s : patch_vol %d -> %d (%s%d)" % (
            os.path.basename(e["path"]), old_pv, new_pv, sign, delta)
        if log:
            log(msg)

    return written
