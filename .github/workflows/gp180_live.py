# -*- coding: utf-8 -*-
"""
GP-180 Studio -- Controle live des parametres + sélecteur de modele.

- Sliders par parametre de chaque slot
- Combobox de selection du modele (ampli, reverb, etc.)
- Push immédiat au relacher du slider (sans debounce)
- Barre de progression chunk par chunk
"""

import os
import struct
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from gp180lib import (decode_prst, checksum,
                          MODULES, MODULE_INDEX, SLOT_ACCEPTS,
                          REC_MAGIC, RECORD_SIZE, N_SLOTS)
    _LIB_OK = True
except ImportError:
    _LIB_OK = False

try:
    from gp180_usb import GP180USB
    _USB_OK = True
except ImportError:
    _USB_OK = False

# ── Constantes ────────────────────────────────────────────────────────────────

SLOT_COLORS = {
    "PRE": "#607D8B", "WAH": "#9E9E9E", "DST": "#FF7043",
    "AMP": "#42A5F5", "NR":  "#78909C", "CAB": "#66BB6A",
    "EQ":  "#AB47BC", "MOD": "#FFA726", "DLY": "#26C6DA",
    "RVB": "#EC407A", "VOL": "#8D6E63",
}
N_COLS = 3   # nombre de colonnes de modules

# ── Helpers .prst en RAM ──────────────────────────────────────────────────────

def _rec0(data):
    idx = data.find(REC_MAGIC)
    if idx < 0: raise ValueError("REC_MAGIC introuvable")
    return idx

def _param_offset(rec0, k, pslot):
    return rec0 + k * RECORD_SIZE + 12 + pslot * 4

def _write_float(data, off, val):
    struct.pack_into("<f", data, off, val)
    struct.pack_into(">H", data, len(data)-2, checksum(data))

def _write_on(data, rec0, k, on):
    data[rec0 + k * RECORD_SIZE + 5] = 1 if on else 0
    struct.pack_into(">H", data, len(data)-2, checksum(data))

def _write_model(data, rec0, k, mid, cat):
    o = rec0 + k * RECORD_SIZE
    struct.pack_into("<H", data, o+8, mid)
    data[o+11] = cat
    struct.pack_into(">H", data, len(data)-2, checksum(data))

def _write_param_defaults(data, rec0, k, params_meta):
    """Ecrit les valeurs par defaut d'un nouveau modele."""
    o = rec0 + k * RECORD_SIZE + 12
    for p in params_meta:
        if p.get("slot", 99) < N_SLOTS:
            struct.pack_into("<f", data, o + p["slot"]*4, float(p.get("default", 0)))
    struct.pack_into(">H", data, len(data)-2, checksum(data))


# ── Fenetre ───────────────────────────────────────────────────────────────────

class LiveControlWindow(tk.Toplevel):

    def __init__(self, parent, prst_path, tables, prst_data=None):
        super().__init__(parent)
        self.title("GP-180 Studio  —  Live Control")
        self.resizable(True, True)
        self.minsize(900, 520)
        self.transient(parent)
        self.lift()

        self._path    = prst_path
        self._tables  = tables
        self._data    = bytearray(prst_data if prst_data else open(prst_path,"rb").read())
        self._rec0    = _rec0(self._data)
        self._usb     = None
        self._pushing = False
        self._push_after = None

        self._v_status = tk.StringVar(value="")
        self._decoded  = decode_prst(prst_path, tables) if _LIB_OK else None

        self._build_ui()
        self._connect_usb()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)   # row 1 = scroll, PAS row 0

        # ── Barre de titre compacte ──
        bar = ttk.Frame(self, padding=(8, 4))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        ttk.Label(bar, text="🎸 Live Control",
                  font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w")

        self._push_bar = ttk.Progressbar(bar, mode="determinate", length=180, maximum=8)
        self._push_bar.grid(row=0, column=1, padx=(10,0), sticky="ew")
        self._push_bar.grid_remove()

        ttk.Label(bar, textvariable=self._v_status,
                  font=("Arial", 9), foreground="#88BBFF").grid(
            row=0, column=2, padx=(10,0))
        ttk.Button(bar, text="↻", width=3,
                   command=self._reload).grid(row=0, column=3, padx=(6,0))

        # ── Zone scrollable ──
        outer = ttk.Frame(self)
        outer.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.grid(row=0, column=0, sticky="nsew")

        self._inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0,0), window=self._inner, anchor="nw")

        def _resize(e): canvas.itemconfig(win_id, width=e.width)
        def _scroll(e): canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _resize)
        self._inner.bind("<Configure>", _scroll)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._build_modules()

    def _build_modules(self):
        for w in self._inner.winfo_children():
            w.destroy()
        if not self._decoded:
            ttk.Label(self._inner, text="Impossible de décoder le preset.",
                      foreground="red").pack(padx=12, pady=12)
            return

        modules = self._decoded.get("modules", {})
        col = row = 0
        for slot_name in MODULES:
            if slot_name not in modules:
                continue
            self._inner.columnconfigure(col, weight=1)
            self._build_slot(slot_name, modules[slot_name], row, col)
            col += 1
            if col >= N_COLS:
                col = 0
                row += 1

    def _build_slot(self, slot_name, mod, row, col):
        k     = MODULE_INDEX[slot_name]
        model = mod.get("model", "?")

        grp = ttk.LabelFrame(self._inner,
                              text=f" {slot_name} ", padding=5)
        grp.grid(row=row, column=col, sticky="nsew", padx=5, pady=4)
        grp.columnconfigure(1, weight=1)

        # ── Ligne 0 : sélecteur de modèle + ON/OFF ──
        on_var = tk.BooleanVar(value=mod.get("on", True))
        ttk.Checkbutton(grp, variable=on_var, text="ON",
                        command=lambda: _write_on(self._data, self._rec0, k, on_var.get()) or self._push_now()
                        ).grid(row=0, column=0, sticky="w")

        # Combobox des modeles disponibles
        model_names, model_map = self._get_models(slot_name)
        cb_model = ttk.Combobox(grp, values=model_names, state="readonly",
                                 width=16, font=("Arial", 8))
        cb_model.set(model)
        cb_model.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0,4))
        cb_model.bind("<<ComboboxSelected>>",
                      lambda e, k=k, sn=slot_name, mm=model_map, cb=cb_model:
                      self._on_model_change(k, sn, mm, cb))

        ttk.Separator(grp, orient="horizontal").grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=3)

        # ── Paramètres ──
        params = mod.get("params", {})
        param_meta = {}
        try:
            for p in self._tables.params_of(mod["model_id"], mod["category"]):
                param_meta[p["name"]] = p
        except Exception:
            pass

        for pi, (pname, pval) in enumerate(params.items()):
            meta  = param_meta.get(pname, {})
            pmin  = float(meta.get("min", 0))
            pmax  = float(meta.get("max", 100))
            pslot = meta.get("slot", pi)
            if pmax <= pmin: pmax = pmin + 100

            r = pi + 2
            ttk.Label(grp, text=pname, font=("Arial", 8),
                      width=11, anchor="w").grid(row=r, column=0, sticky="w")

            v_disp = tk.StringVar(value=f"{pval:.0f}")
            ttk.Label(grp, textvariable=v_disp, font=("Courier", 8),
                      width=6, anchor="e").grid(row=r, column=2, sticky="e")

            sc = ttk.Scale(grp, from_=pmin, to=pmax,
                           orient="horizontal", value=pval)
            sc.grid(row=r, column=1, sticky="ew", padx=3)

            # Mise à jour visuelle instantanée
            sc.bind("<Motion>", lambda e, vd=v_disp:
                    vd.set(f"{float(e.widget.get()):.0f}"))
            # Push au relâcher seulement
            sc.bind("<ButtonRelease-1>",
                    lambda e, k=k, ps=pslot, vd=v_disp:
                    self._on_release(e.widget, k, ps, vd))

    # ── Modeles disponibles par slot ──────────────────────────────────────────

    def _get_models(self, slot_name):
        """Retourne (liste_noms, {nom: (mid, cat)}) pour le slot."""
        names = []
        mapping = {}
        try:
            if slot_name == "CAB":
                for c in self._tables.cabs:
                    if not c.get("user_slot"):
                        n = c["name"]
                        names.append(n)
                        mapping[n] = (c["model_id"], 10)
            else:
                cats = SLOT_ACCEPTS.get(slot_name, [])
                seen = set()
                for (cat, mid), m in self._tables.by_key.items():
                    if cat in cats:
                        n = m.get("name", f"#{mid}")
                        if n not in seen:
                            seen.add(n)
                            names.append(n)
                            mapping[n] = (mid, cat)
        except Exception:
            pass
        return sorted(names), mapping

    def _on_model_change(self, k, slot_name, model_map, cb):
        """Change le modele du slot et recharge les params."""
        name = cb.get()
        if name not in model_map:
            return
        mid, cat = model_map[name]
        _write_model(self._data, self._rec0, k, mid, cat)
        # Ecrire les valeurs par defaut du nouveau modele
        try:
            params_meta = self._tables.params_of(mid, cat)
            _write_param_defaults(self._data, self._rec0, k, params_meta)
        except Exception:
            pass
        # Recharger le decode et reconstruire l'UI
        try:
            self._decoded = decode_prst(self._path, self._tables)
            # Sauvegarder le fichier temporairement pour le redecode
            # (on relit depuis self._data en mémoire)
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".prst", delete=False) as tf:
                tf.write(self._data)
                tmp = tf.name
            self._decoded = decode_prst(tmp, self._tables)
            os.unlink(tmp)
        except Exception:
            pass
        self._build_modules()
        self._push_now()

    # ── Slider callbacks ──────────────────────────────────────────────────────

    def _on_release(self, widget, k, pslot, v_disp):
        val = float(widget.get())
        v_disp.set(f"{val:.0f}")
        off = _param_offset(self._rec0, k, pslot)
        _write_float(self._data, off, val)
        self._push_now()

    def _push_now(self):
        """Push immédiat (pas de debounce) si pas déjà en cours."""
        if self._pushing:
            return
        self._pushing = True
        self._v_status.set("⏳ Envoi…")
        self._push_bar["value"] = 0
        self._push_bar.grid()
        data_copy = bytes(self._data)
        threading.Thread(target=self._push_bg, args=(data_copy,), daemon=True).start()

    def _push_bg(self, data):
        def progress(step, total, label):
            self.after(0, lambda s=step, t=total: self._on_progress(s, t))
        try:
            self._usb.write_preset(1, "A", data,
                                   progress_cb=progress,
                                   inter_chunk_delay=0.005,
                                   handshake_delay=0.03)
            import time; time.sleep(0.05)
            self._usb.select_preset(1, "A")
            self.after(0, self._on_done)
        except Exception as ex:
            self.after(0, lambda e=str(ex): self._on_error(e))

    def _on_progress(self, step, total):
        if step == 0:
            self._push_bar["maximum"] = total + 1
            self._push_bar["value"]   = 0
            self._v_status.set("📡")
        else:
            self._push_bar["value"] = step
            self._v_status.set(f"📤 {step}/{total}")

    def _on_done(self):
        self._push_bar["value"] = self._push_bar["maximum"]
        self.after(250, lambda: (self._push_bar.grid_remove(),
                                  self._v_status.set("✅ 01-A")))
        self._pushing = False

    def _on_error(self, err):
        self._push_bar.grid_remove()
        self._v_status.set(f"❌ {err[:40]}")
        self._pushing = False

    # ── USB + Reload ──────────────────────────────────────────────────────────

    def _connect_usb(self):
        if not _USB_OK:
            self._v_status.set("⚫ USB indisponible")
            return
        dev = GP180USB(verbose=False)
        if dev.connect():
            self._usb = dev
            self._v_status.set("🔵 GP-180 prêt")
        else:
            self._v_status.set("⚫ GP-180 non détecté")

    def _reload(self):
        try:
            self._data    = bytearray(open(self._path,"rb").read())
            self._rec0    = _rec0(self._data)
            self._decoded = decode_prst(self._path, self._tables)
            self._build_modules()
            self._v_status.set("↻ Rechargé")
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)

    def _on_close(self):
        if self._usb:
            try: self._usb.disconnect()
            except: pass
        self.destroy()
