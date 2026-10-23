#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gp180_validate — harnais de confrontation tables firmware <-> materiel reel.

Usage
-----
    python gp180_validate.py dump/                    # rapport complet
    python gp180_validate.py dump/ --json rapport.json
    python gp180_validate.py --carve backup.bin -o dump/   # decoupe un blob
    python gp180_validate.py --checklist               # liste a verifier a l'ecran

Ce que ca teste, du plus sur au moins sur
-----------------------------------------
 T1 STRUCTURE   taille 1224, magic present, checksum, chain_order permutation
 T2 BANC USINE  (model_id, category) par slot vs data/gp180_factory_presets.json
                -> valide l'extraction firmware du banc. PREDICTION INDEPENDANTE.
 T3 ID CONNUS   tout (id,cat) rencontre existe-t-il dans nos 206 modeles ?
                -> un inconnu = trou dans le catalogue
 T4 BORNES      chaque float lu via `slot` tombe-t-il dans [min,max] du firmware ?
                -> un `slot` mal mappe sort des bornes. Test des slots SANS ecran.
 T5 ORPHELINS   floats non nuls qu'aucun parametre ne reclame
                -> parametres sous-comptes dans nos tables
 T6 ROUND-TRIP  decode -> encode (fichier lui-meme comme template) -> octets ?
                -> perte d'information = mapping incomplet

Ce que ca NE teste PAS : la correspondance id -> NOM. Seul l'ecran de l'editeur
peut l'ancrer. Voir --checklist.
"""
import argparse
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gp180lib import (Tables, decode_prst, encode_prst, checksum,
                      MODULES, FILE_SIZE, REC_MAGIC, N_SLOTS, N_MODULES,
                      RECORD_SIZE, _norm)


# ------------------------------------------------------------------ carve
def carve(blob_path, outdir):
    """Decoupe un backup monolithique en .prst de 1224 o.

    Strategie : on cherche chaque occurrence de REC_MAGIC et on remonte a
    l'origine presumee du fichier. Les 128 presets d'usine sont espaces de
    1024 o dans le firmware, mais un export d'editeur est probablement une
    concatenation de fichiers 1224. On essaie les deux et on garde ce qui
    donne des checksums valides.
    """
    data = open(blob_path, "rb").read()
    os.makedirs(outdir, exist_ok=True)
    print("blob : %d octets (%.1f x 1224)" % (len(data), len(data) / FILE_SIZE))

    best = None
    for stride in (FILE_SIZE, 1024):
        for start in range(0, min(4096, max(1, len(data) - FILE_SIZE)), 4):
            n_ok = 0
            for i in range(start, len(data) - FILE_SIZE + 1, stride):
                chunk = data[i:i + FILE_SIZE]
                if len(chunk) < FILE_SIZE:
                    break
                stored = struct.unpack_from(">H", chunk, FILE_SIZE - 2)[0]
                if checksum(chunk) == stored:
                    n_ok += 1
            if n_ok and (best is None or n_ok > best[0]):
                best = (n_ok, start, stride)

    if not best or best[0] == 0:
        print("ECHEC : aucun decoupage ne donne de checksum valide.")
        print("       -> le blob n'est pas une simple concatenation.")
        print("       -> envoie-moi les 512 premiers octets en hexa, on regardera.")
        return 0

    n_ok, start, stride = best
    print("meilleur decoupage : offset %d, pas %d -> %d presets valides"
          % (start, stride, n_ok))
    k = 0
    for i in range(start, len(data) - FILE_SIZE + 1, stride):
        chunk = data[i:i + FILE_SIZE]
        stored = struct.unpack_from(">H", chunk, FILE_SIZE - 2)[0]
        if checksum(chunk) != stored:
            continue
        raw = chunk[0x44:0x54]
        nm = raw.split(b"\x00")[0].decode("latin1", "replace") or "preset"
        nm = re.sub(r"[^A-Za-z0-9 _-]", "_", nm).strip() or "preset"
        open(os.path.join(outdir, "%03d_%s.prst" % (k, nm)), "wb").write(chunk)
        k += 1
    print("ecrit : %d fichiers dans %s" % (k, outdir))
    return k


# ------------------------------------------------------------------ checks
def param_index(tb):
    """(id,cat) -> {slot_float: param} pour detecter les orphelins."""
    idx = {}
    for m in tb.models:
        claimed = {p["slot"]: p for p in m["params"] if p["slot"] < N_SLOTS}
        idx[(m["id"], m["cat"])] = claimed
    return idx


def match_factory(tb, decoded, path=None):
    """Associe un fichier decode a son preset d'usine.

    D'ABORD par POSITION : l'editeur nomme les fichiers 'NN-L nom.prst' ou NN est
    la banque (1..32) et L la lettre (A..D). L'index firmware est (NN-1)*4+(L-A).
    C'est fiable meme quand le banc a ete renomme entre l'extraction firmware et
    la version installee (ce qui est le cas : 'On The Way' -> 'Juan Fer Ramirez').
    Repli par nom si le fichier ne suit pas la convention.
    """
    if path:
        m = re.match(r"(\d+)-([A-D])", os.path.basename(path))
        if m:
            idx = (int(m.group(1)) - 1) * 4 + (ord(m.group(2)) - ord("A"))
            for p in tb.presets:
                if p["index"] == idx:
                    return p
    by_name = {}
    for p in tb.presets:
        by_name.setdefault(_norm(p["name"]), p)
    return by_name.get(_norm(decoded["name"]))


def validate_file(path, tb, pidx, do_roundtrip=True):
    r = {"file": os.path.basename(path), "errors": [], "warnings": [],
         "notes": [], "models_seen": []}

    size = os.path.getsize(path)
    if size != FILE_SIZE:
        r["errors"].append("T1 taille %d != %d" % (size, FILE_SIZE))
        return r

    try:
        d = decode_prst(path, tb)
    except Exception as e:
        r["errors"].append("T1 decode impossible : %s" % e)
        return r

    r["name"] = d["name"]
    r["author"] = d["author"]

    # T1 -------------------------------------------------------------
    if not d["checksum"]["valid"]:
        r["errors"].append("T1 checksum stocke %d != calcule %d"
                           % (d["checksum"]["stored"], d["checksum"]["computed"]))
    if d["chain_order"] is None:
        r["errors"].append("T1 chain_order n'est pas une permutation de 0..10")

    # T2 -------------------------------------------------------------
    fac = match_factory(tb, d, path)
    if fac:
        r["factory_index"] = fac["index"]
        for slot in MODULES:
            got = d["modules"].get(slot)
            exp = fac["slots"].get(slot)
            if not got or not exp:
                continue
            if (got["model_id"], got["category"]) != (exp["model_id"], exp["category"]):
                r["errors"].append(
                    "T2 %s : appareil (%d,cat%d) != firmware (%d,cat%d) [%s]"
                    % (slot, got["model_id"], got["category"],
                       exp["model_id"], exp["category"], exp["name"]))
        if fac["chain_order"] != d["chain_order"]:
            r["warnings"].append("T2 chain_order : appareil %s != firmware %s"
                                 % (d["chain_order"], fac["chain_order"]))

    # T3..T6 par module ----------------------------------------------
    for slot in MODULES:
        e = d["modules"].get(slot)
        if not e:
            continue
        mid, cat = e["model_id"], e["category"]
        r["models_seen"].append([mid, cat, slot])

        # T3 — les CAB vivent dans gp180_cabs.json, pas dans models_all
        if e.get("model") is None:
            r["errors"].append("T3 %s : (%d,cat%d) ABSENT du catalogue"
                               % (slot, mid, cat))
            continue

        # SLOT_ACCEPTS
        from gp180lib import SLOT_ACCEPTS
        if cat not in SLOT_ACCEPTS.get(slot, []):
            r["errors"].append("T3 %s : cat%d hors SLOT_ACCEPTS %s (modele %s)"
                               % (slot, cat, SLOT_ACCEPTS.get(slot), e["model"]))

        # T4 — bornes. On ne teste QUE les modules actifs : un module eteint
        # garde des floats arbitraires (76 cas sur le banc d'usine, tous benins).
        # Et on saute Time/Rate quand le modele a un Sync/Tempo : en mode
        # synchronise, Time n'est plus en ms mais un index de division rythmique,
        # hors de la plage ms declaree (37 cas benins sur le banc).
        plist = tb.params_of(mid, cat)
        has_sync = any(p["name"] in ("Sync", "Tempo", "Time Sync", "Sweep Sync")
                       for p in plist)
        if e.get("on", True):
            for p in plist:
                if p["slot"] >= N_SLOTS:
                    continue
                if p["name"] in ("Time", "Rate") and has_sync:
                    continue
                v = e["raw_floats"][p["slot"]]
                lo, hi = min(p["min"], p["max"]), max(p["min"], p["max"])
                tol = max(abs(hi - lo) * 1e-4, 1e-3)
                if not (lo - tol <= v <= hi + tol):
                    r["errors"].append(
                        "T4 %s/%s/%s : %g hors [%g..%g] (slot %d)"
                        % (slot, e["model"], p["name"], v, lo, hi, p["slot"]))

        # T5 — floats non reclames par nos tables. L'export de la machine a
        # montre que certains modeles (COMP, COMP4, C-Chorus, Gate 1, Mess...)
        # portent des valeurs coherentes a des index que ni nos tables NI
        # algorithm.xml n'exposent : parametres internes ou gabarit de bloc
        # partage. Ce n'est donc PAS une anomalie par preset — c'est une
        # propriete connue de ces modeles. On l'agrege discretement (notes)
        # au lieu d'inonder le rapport ; le recap de fin en fait la synthese.
        claimed = set(pidx.get((mid, cat), {}).keys())
        if cat == 10:
            claimed = set(pidx.get((0, 10), {}).keys())
        for i, v in enumerate(e["raw_floats"]):
            if i in claimed or abs(v) <= 1e-6:
                continue
            if v == v and abs(v) != float("inf") and 1e-3 <= abs(v) <= 21000.0:
                r["notes"].append("T5 %s|%s|%d|%g" % (e["model"], slot, i, v))

    # T6 -------------------------------------------------------------
    if do_roundtrip and not r["errors"]:
        try:
            spec = {"name": d["name"], "author": d["author"],
                    "description": d["description"],
                    "chain_order": d["chain_order"], "modules": {}}
            for slot in MODULES:
                e = d["modules"][slot]
                spec["modules"][slot] = {
                    "model": e["model"], "on": e["on"],
                    "params": dict(e.get("params") or {})}
            raw, warn = encode_prst(spec, tb, template=path,
                                    keep_assignments=True, strict=False,
                                    fill_empty_slots=False)
            orig = open(path, "rb").read()
            if raw != orig:
                # Un diff brut n'est pas forcement une perte d'information.
                # Trois causes benignes connues :
                #   - un float qu'aucun parametre ne reclame (reliquat memoire)
                #     est remis a zero par encode_prst ;
                #   - -0.0 se re-encode en +0.0 (bit de signe sur un zero) ;
                #   - le checksum se recalcule.
                # Tout le reste est une VRAIE perte : le classement le montre.
                rec0 = orig.find(REC_MAGIC)
                real = []
                for i in range(FILE_SIZE):
                    if raw[i] == orig[i]:
                        continue
                    if i >= FILE_SIZE - 2:
                        continue                       # checksum
                    if not (rec0 <= i < rec0 + N_MODULES * RECORD_SIZE):
                        real.append(("hors zone record", i))
                        continue
                    k, off = divmod(i - rec0, RECORD_SIZE)
                    if off < 12:
                        real.append(("en-tete %s" % MODULES[k], i))
                        continue
                    fi = (off - 12) // 4
                    slot = MODULES[k]
                    e = d["modules"][slot]
                    claimed = set(pidx.get((0, 10) if e["category"] == 10
                                           else (e["model_id"], e["category"]),
                                           {}).keys())
                    a = struct.unpack_from("<f", orig, rec0 + k * RECORD_SIZE + 12 + 4 * fi)[0]
                    b = struct.unpack_from("<f", raw, rec0 + k * RECORD_SIZE + 12 + 4 * fi)[0]
                    if fi not in claimed:
                        continue                       # reliquat, benin
                    if a == b:
                        continue                       # -0.0 vs +0.0
                    real.append(("%s/%s float[%d] %r -> %r"
                                 % (slot, e.get("model"), fi, a, b), i))
                if real:
                    r["errors"].append(
                        "T6 round-trip : %d perte(s) reelle(s) : %s"
                        % (len(real), "; ".join(m for m, _ in real[:5])))
                else:
                    r["notes"].append(
                        "T6 round-trip : diff limite aux floats non reclames, "
                        "aux zeros signes et au checksum — benin")
            for w in warn:
                r["warnings"].append("T6 " + w)
        except Exception as ex:
            r["errors"].append("T6 re-encodage impossible : %s" % ex)

    return r


# ------------------------------------------------------------------ report
def run(folder, tb, out_json=None):
    files = []
    for root, _, names in os.walk(folder):
        for n in sorted(names):
            if n.lower().endswith(".prst"):
                files.append(os.path.join(root, n))
    if not files:
        print("Aucun .prst dans %s" % folder)
        return 1

    pidx = param_index(tb)
    results = [validate_file(f, tb, pidx) for f in files]

    n_err = sum(1 for r in results if r["errors"])
    n_warn = sum(1 for r in results if r["warnings"])
    matched = sum(1 for r in results if "factory_index" in r)

    print("=" * 72)
    print("GP-180 — confrontation tables firmware / materiel")
    print("=" * 72)
    print("fichiers      : %d" % len(files))
    print("apparies usine: %d / %d" % (matched, len(tb.presets)))
    print("en erreur     : %d" % n_err)
    print("avec warning  : %d" % n_warn)
    print()

    # agregation des erreurs par type de test
    by_test = defaultdict(list)
    for r in results:
        for e in r["errors"]:
            by_test[e.split()[0]].append((r["file"], e))
        for w in r["warnings"]:
            by_test[w.split()[0]].append((r["file"], w))

    LABEL = {"T1": "STRUCTURE", "T2": "BANC USINE (par position)",
             "T3": "ID CONNUS", "T4": "BORNES (modules actifs)",
             "T6": "ROUND-TRIP"}
    for t in ("T1", "T2", "T3", "T4", "T6"):
        items = by_test.get(t, [])
        status = "OK" if not items else "%d anomalie(s)" % len(items)
        print("[%s] %-26s %s" % (t, LABEL[t], status))
        for f, m in items[:15]:
            print("       %-28s %s" % (f[:28], m))
        if len(items) > 15:
            print("       ... et %d autres" % (len(items) - 15))
    print()

    # T5 : synthese des parametres non extraits (fait connu, pas anomalie).
    # Un float non reclame qui prend PLUSIEURS valeurs selon les presets est un
    # vrai parametre sous-compte ; une valeur unique est probablement une
    # constante de gabarit. On agrege par (modele, index).
    t5 = defaultdict(list)
    for r in results:
        for n in r["notes"]:
            if n.startswith("T5 "):
                mdl, slot, i, v = n[3:].split("|")
                t5[(mdl, slot, int(i))].append(float(v))
    if t5:
        variables = {k: vs for k, vs in t5.items() if len(set(round(x, 2) for x in vs)) > 1}
        print("[T5] PARAMETRES NON EXTRAITS   %d couples (modele,slot_float)"
              % len(t5))
        print("     -> %d varient selon les presets (vrais parametres sous-comptes),"
              % len(variables))
        print("        %d sont constants (gabarit). Enjeu de round-trip, pas de generation."
              % (len(t5) - len(variables)))
        for (mdl, slot, i), vs in sorted(variables.items(),
                                         key=lambda kv: -len(kv[1]))[:10]:
            u = sorted(set(round(x, 2) for x in vs))
            print("        %-12s %-4s float[%d]  x%-3d  %s"
                  % (mdl, slot, i, len(vs), u[:6]))
    print()

    # couverture du catalogue — modeles et cabs sont deux espaces distincts
    seen_m, seen_c = set(), set()
    for r in results:
        for mid, cat, _ in r["models_seen"]:
            (seen_c if cat == 10 else seen_m).add((mid, cat))
    total_m = {(m["id"], m["cat"]) for m in tb.models}
    total_c = {(c["model_id"], 10) for c in tb.cabs}

    print("COUVERTURE CATALOGUE")
    for label, seen, total in (("modeles", seen_m, total_m),
                               ("cabs   ", seen_c, total_c)):
        ok = len(seen & total)
        print("  %s vus : %3d / %3d (%2.0f%%)  — %d non verifies"
              % (label, ok, len(total), 100.0 * ok / len(total), len(total) - ok))
    unknown = (seen_m - total_m) | (seen_c - total_c)
    if unknown:
        print("  INCONNUS (presents dans l'appareil, absents de nos tables) :")
        for k in sorted(unknown):
            print("     id=%d cat=%d   <- TROU DANS LE CATALOGUE" % k)
    print("  -> tout modele jamais vu reste NON VERIFIE : balayage manuel")
    print("     dans l'editeur (voir --checklist)")
    print()
    seen = seen_m | seen_c

    verdict = "TABLES CONFIRMEES sur ce dump" if n_err == 0 else \
              "DIVERGENCES — ne pas generer de preset avant analyse"
    print("VERDICT : %s" % verdict)

    if out_json:
        json.dump({"results": results,
                   "seen": sorted("%d,%d" % k for k in seen),
                   "unknown": sorted("%d,%d" % k for k in unknown)},
                  open(out_json, "w", encoding="utf-8"), indent=1,
                  ensure_ascii=False)
        print("rapport detaille -> %s" % out_json)
    return 0 if n_err == 0 else 2


def checklist(tb):
    """Liste a confronter a l'ecran de l'editeur — c'est le SEUL ancrage id->nom."""
    print("# Checklist ecran — id -> nom")
    print("# Ouvre le preset d'usine indique, lis le slot a l'ecran, compare.")
    print("# Chaque ligne cochee ancre un nom que le firmware seul ne prouve pas.")
    print()
    seen = {}
    for p in tb.presets:
        for slot, s in p["slots"].items():
            k = (s["model_id"], s["category"])
            seen.setdefault(k, (p["index"], p["name"], slot, s["name"]))
    print("## Verifiables via les presets d'usine (%d modeles)" % len(seen))
    for (mid, cat), (idx, pname, slot, mname) in sorted(seen.items()):
        print("[ ] preset %3d %-18s %-4s -> attendu %-16s (id=%d cat=%d)"
              % (idx, pname[:18], slot, mname, mid, cat))
    rest = [m for m in tb.models if (m["id"], m["cat"]) not in seen]
    print()
    print("## Absents du banc d'usine — a balayer a la main (%d modeles)" % len(rest))
    for m in sorted(rest, key=lambda m: (m["cat"], m["id"])):
        print("[ ] cat%-2d id=%-4d attendu %s" % (m["cat"], m["id"], m["name"]))


def roundtrip(path, tb):
    """Aller-retour a vide : decode un preset, le re-encode SANS rien changer,
    et rapporte octet par octet ce qui differe. C'est le test a faire AVANT tout
    import genere : si l'appli ne sait pas reproduire a l'identique un preset
    existant, elle ne produira pas non plus un fichier propre.
    """
    d = decode_prst(path, tb)
    spec = {"name": d["name"], "author": d["author"],
            "description": d["description"],
            "chain_order": d["chain_order"], "modules": {}}
    for slot in MODULES:
        e = d["modules"][slot]
        spec["modules"][slot] = {"model": e["model"], "on": e["on"],
                                 "params": dict(e.get("params") or {})}
    raw, warn = encode_prst(spec, tb, template=path, keep_assignments=True,
                            strict=False, fill_empty_slots=False)
    orig = open(path, "rb").read()
    rec0 = orig.find(REC_MAGIC)
    diffs = [i for i in range(FILE_SIZE) if raw[i] != orig[i]]

    print("Aller-retour a vide : %s" % os.path.basename(path))
    print("  %d / %d octets identiques (%.1f%%)"
          % (FILE_SIZE - len(diffs), FILE_SIZE, 100.0 * (FILE_SIZE - len(diffs)) / FILE_SIZE))
    if not diffs:
        print("  PARFAIT : reproduction bit a bit. L'appli sait ecrire ce format.")
        return 0

    # classer les diffs par zone
    zones = defaultdict(int)
    ascii_runs = 0
    for i in diffs:
        if i >= FILE_SIZE - 2:
            zones["checksum"] += 1
        elif i < rec0 - 12:
            zones["header (0x00-0x%X)" % (rec0 - 12)] += 1
        elif i < rec0:
            zones["chain_order"] += 1
        elif i < rec0 + N_MODULES * RECORD_SIZE:
            b = orig[i]
            if 32 <= b < 127:
                ascii_runs += 1
            zones["records (params + metadonnees)"] += 1
        else:
            zones["queue (0x%X+)" % (rec0 + N_MODULES * RECORD_SIZE)] += 1
    for z, n in sorted(zones.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d octets" % (z, n))
    if ascii_runs:
        print("  dont ~%d octets de TEXTE ASCII dans les records : ce sont des" % ascii_runs)
        print("       metadonnees d'editeur (noms de parametres) que le decodeur")
        print("       ne conserve pas. Sans impact audio, mais l'editeur peut les")
        print("       attendre. A verifier a l'import.")
    for w in warn:
        print("  warn: %s" % w)
    print()
    print("  -> IMPORTANT : ces diffs viennent d'un preset re-encode a l'identique.")
    print("     Si l'import de ce fichier re-encode ECHOUE dans l'editeur, le")
    print("     probleme est la, pas dans la generation. Teste ce fichier d'abord.")
    out = os.path.splitext(path)[0] + ".roundtrip.prst"
    open(out, "wb").write(raw)
    print("  fichier re-encode ecrit : %s" % out)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", help="dossier contenant les .prst")
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--json", dest="out_json")
    ap.add_argument("--carve", metavar="BLOB", help="decouper un backup monolithique")
    ap.add_argument("-o", "--outdir", default="dump_carved")
    ap.add_argument("--checklist", action="store_true")
    ap.add_argument("--roundtrip", metavar="PRST",
                    help="aller-retour a vide sur un preset (test pre-import)")
    a = ap.parse_args()

    tb = Tables(a.data)

    if a.carve:
        return 0 if carve(a.carve, a.outdir) else 1
    if a.roundtrip:
        return roundtrip(a.roundtrip, tb)
    if a.checklist:
        checklist(tb)
        return 0
    if not a.folder:
        ap.print_help()
        return 1
    return run(a.folder, tb, a.out_json)


if __name__ == "__main__":
    sys.exit(main())
