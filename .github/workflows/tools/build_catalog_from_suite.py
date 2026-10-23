#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Konversi module_data.json (Valeton Suite V2.1.0) -> data/gp180_models_suite.json
dalam format yang sama dengan gp180_models_all.json.

Usage: python tools/build_catalog_from_suite.py [module_data.json] [out.json]

Catatan:
 * fxid = (cat << 24) | id  -- sama dengan konvensi GP-200 (157 entri identik id/cat/param).
 * slot = algId ; type_code = angka dari "ValToStr_NNN" ; unit_code diambil dari katalog
   GP-200 bila model+parameter sama, selain itu 0 (BELUM DIKETAHUI).
 * Sumber: aset Suite; file ini memuat 12 modul GP-180 (PRE, WAH, DST, N->S, AMP, NR,
   CAB, EQ, MOD, DLY, RVB, VOL).  'N->S' = pemuatan NAM/SnapTone.
"""
import json, os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "data", "gp180_suite", "module_data.json")
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "data", "gp180_models_suite.json")
suite = json.load(open(src, encoding="utf-8"))
g200 = json.load(open(os.path.join(root, "data", "gp180_models_all.json"), encoding="utf-8"))
by_key = {(m["id"], m["cat"]): m for m in g200}
out = []
for mod in suite["modules"]:
    for e in mod["module"]:
        cat, id_ = e["fxid"] >> 24, e["fxid"] & 0xFFFFFF
        ref = by_key.get((id_, cat))
        refp = {p["name"]: p for p in ref["params"]} if ref else {}
        params = []
        for i, a in enumerate(e["alg"]):
            m = re.search(r"(\d+)\s*$", a.get("code", ""))
            rp = refp.get(a["name"])
            params.append(dict(name=a["name"], slot=a["algId"], ui_order=i,
                min=float(a["min"]), max=float(a["max"]), step=float(a["step"]),
                default=float(a["defaultValue"]),
                unit_code=rp["unit_code"] if rp else 0,
                type_code=int(m.group(1)) if m else 0,
                code=a.get("code"), widget=a.get("widgetType")))
        out.append(dict(id=id_, cat=cat, fxid=e["fxid"], catname=mod["name"], module=mod["name"],
            name=e["name"], title=e["fxtitle"], category_label=e["type"], origin=e["origin"],
            n_params=len(params), params=params, slots=[mod["name"]],
            defcab=ref.get("defcab") if ref else None, in_gp200_catalog=bool(ref),
            description_en=e["descriptionEn"], summary_en=e["summaryEn"].strip(),
            source="Valeton Suite V2.1.0 module_data.json"))
json.dump(out, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
from collections import Counter
print(len(out), "entri ->", dst); print(Counter(m["module"] for m in out))
