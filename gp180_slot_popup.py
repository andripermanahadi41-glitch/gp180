# -*- coding: utf-8 -*-
"""
GP-180 Studio — Popup de contrôle live d'un slot du SignalRack.

S'ouvre au clic sur une carte du rack ; une seule popup à la fois.
Header coloré selon le type de slot, sliders live via send_param_update().
"""

import tkinter as tk
from tkinter import ttk

try:
    from gp180_usb import GP180USB
    _USB_OK = True
except ImportError:
    _USB_OK = False
    GP180USB = None

try:
    from gp180_lib import SLOT_ACCEPTS
    _SLOT_ACCEPTS_OK = True
except ImportError:
    try:
        from gp180lib import SLOT_ACCEPTS, REC_MAGIC
        _SLOT_ACCEPTS_OK = True
    except ImportError:
        _SLOT_ACCEPTS_OK = False
        SLOT_ACCEPTS = {}
        REC_MAGIC = b'\x14\x00\x44\x00'

try:
    from gp180_theme import TOK, FONT
    _BG       = TOK["bg_panel"]
    _BG_FIELD = TOK["bg_field"]
    _INK      = TOK["ink"]
    _INK_DIM  = TOK["ink_dim"]
except Exception:
    _BG = _BG_FIELD = "#1E1E2E"
    _INK = "#E0E0E0"
    _INK_DIM = "#888888"
    FONT = {"body": ("Arial", 9), "mono": ("Courier New", 9)}

# ── Couleurs par slot — cohérentes avec gp180_live.py et le theme ──────────
SLOT_COLORS = {
    "PRE": "#546E7A",   # bleu-gris
    "WAH": "#78909C",   # gris
    "DST": "#E64A19",   # orange foncé
    "AMP": "#1565C0",   # bleu
    "NR":  "#37474F",   # gris foncé
    "CAB": "#2E7D32",   # vert
    "EQ":  "#6A1B9A",   # violet
    "MOD": "#E65100",   # orange
    "DLY": "#00838F",   # cyan
    "RVB": "#880E4F",   # rose foncé
    "VOL": "#4E342E",   # marron
}

# Couleur du texte sur le header selon la luminosité du fond
SLOT_TEXT = {k: "#FFFFFF" for k in SLOT_COLORS}


def _param_range(pname: str, pval: float):
    """Estime la plage (min, max) du slider selon le nom et la valeur."""
    pn = pname.lower()
    # Valeurs binaires
    if pn in ("trail", "sync") or (abs(pval) <= 1.0 and abs(pval) >= 0
                                    and pn not in ("mix", "volume")):
        return 0.0, 1.0
    # Valeurs en millisecondes (time, decay, pre delay...)
    if "time" in pn or "delay" in pn or "decay" in pn:
        top = max(pval * 2.0, 1000.0)
        return 0.0, top
    # Valeur actuelle > 100 → on double
    if abs(pval) > 100:
        return 0.0, max(pval * 2.0, 200.0)
    return 0.0, 100.0


class SlotControlPopup(tk.Toplevel):
    """
    Popup flottante de contrôle live d'un slot du SignalRack.

    Paramètres :
        parent      : fenêtre parente (App)
        slot_data   : dict {"slot":str, "model":str, "on":bool, "params":{...}}
        module_idx  : index 0-10 du slot dans la chaîne (MODULES.index)
        prst_data   : bytes du .prst courant (pour b8 dynamique) — optionnel
        rec0        : offset REC_MAGIC dans prst_data
        on_close_cb : callable appelé à la fermeture (pour nettoyer la référence)
    """

    def __init__(self, parent, slot_data: dict, module_idx: int,
                 prst_data: bytes = None, rec0: int = None,
                 on_close_cb=None, tables=None, prst_path: str = None):
        super().__init__(parent)
        self._slot      = slot_data
        self._k         = module_idx
        self._prst      = bytearray(prst_data) if prst_data else None
        # Sécurisation de l'offset du bloc : 72 est l'offset standard GP-180
        if self._prst and (rec0 is None or rec0 < 0):
            self._rec0 = 72
        else:
            self._rec0 = rec0
        self._on_close  = on_close_cb
        self._tables    = tables
        self._prst_path = prst_path
        self._usb       = None
        self._sliders   = []
        self._frm_params = None  # frame des sliders (reconstruit au changement de modèle)

        slot_name = slot_data.get("slot", "?")
        model     = slot_data.get("model", "")
        color     = SLOT_COLORS.get(slot_name, "#546E7A")
        ink       = SLOT_TEXT.get(slot_name, "#FFFFFF")

        self.title(f"{slot_name}  —  {model}")
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.configure(bg=_BG)

        self._build_ui(slot_name, model, color, ink)
        self._connect_usb()
        self._place_near_parent(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_destroy)

    # ── Construction UI ────────────────────────────────────────────────────

    def _build_ui(self, slot_name, model, color, ink):
        # ── Header coloré ──────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=color, height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr,
                 text=f"  {slot_name}",
                 bg=color, fg=ink,
                 font=("Arial", 10, "bold")
                 ).pack(side="left", padx=(10, 4))

        # Combobox sélecteur de modèle
        model_names, self._model_map = self._get_models(slot_name)
        self._cb_model = ttk.Combobox(hdr, values=model_names,
                                       state="readonly", width=18,
                                       font=("Arial", 8))
        self._cb_model.set(model)
        self._cb_model.pack(side="left", padx=(0, 8))
        self._cb_model.bind("<<ComboboxSelected>>",
                            lambda e: self._on_model_change(slot_name))

        # Toggle ON/OFF dans le header
        on_state = self._slot.get("on", True)
        self._v_on = tk.BooleanVar(value=on_state)
        tk.Checkbutton(hdr, text="ON",
                       variable=self._v_on,
                       command=self._on_toggle,
                       bg=color, fg=ink,
                       selectcolor=color,
                       activebackground=color,
                       activeforeground=ink,
                       font=("Arial", 9, "bold"),
                       highlightthickness=0, bd=0
                       ).pack(side="right", padx=12)

        # ── Sliders ────────────────────────────────────────────────────────
        self._build_params(self._slot.get("params") or {})

        # ── Bouton Save ────────────────────────────────────────────────────
        self._dirty = False
        btn_frame = tk.Frame(self, bg=_BG)
        btn_frame.pack(fill="x", padx=10, pady=(6, 0))
        self._btn_save = tk.Button(
            btn_frame, text="💾 Sauvegarder dans slot 1-A",
            bg="#1B5E20", fg="#FFFFFF",
            font=("Arial", 8, "bold"),
            relief="flat", bd=0, padx=8, pady=3,
            command=self._on_save)
        self._btn_save.pack(side="left")

        # ── Status bar ─────────────────────────────────────────────────────
        self._v_status = tk.StringVar(value="")
        tk.Label(self, textvariable=self._v_status, bg=_BG, fg=_INK_DIM,
                 font=("Arial", 8), anchor="w"
                 ).pack(fill="x", padx=10, pady=(2, 6))
                 
                 
    def _sync_param_value(self, param_name: str, val: float, param_idx: int = None):
        """Met à jour la valeur dans le tampon binaire ET dans l'application principale (App)."""
        # 1. Mise à jour directe et sécurisée du binaire de la popup self._prst via son index exact
        if self._prst and self._rec0 is not None and param_idx is not None:
            import struct
            blk = self._rec0 + self._k * 72
            struct.pack_into("<f", self._prst, blk + 12 + param_idx * 4, val)
            try:
                from gp180lib import checksum as _cksum
                struct.pack_into(">H", self._prst, len(self._prst) - 2, _cksum(self._prst))
            except Exception:
                pass

        # 2. Mise à jour de la mémoire de l'application principale (gp180_studio)
        try:
            if hasattr(self.master, "_gen") and hasattr(self.master.presets, "_sel"):
                sel = self.master.presets._sel
                if 0 <= sel < len(self.master._gen):
                    gen_item = self.master._gen[sel]
                    slot_name = self._slot.get("slot")
                    if "modules" in gen_item and slot_name in gen_item["modules"]:
                        mod_dict = gen_item["modules"][slot_name]
                        if mod_dict and "params" in mod_dict:
                            mod_dict["params"][param_name] = val
        except Exception:
            pass   
     

    def _build_params(self, params: dict):
        """Construit (ou reconstruit) la zone de sliders."""
        if self._frm_params:
            self._frm_params.destroy()
        self._sliders.clear()

        self._frm_params = tk.Frame(self, bg=_BG, padx=12, pady=10)
        self._frm_params.pack(fill="x")

        if not params:
            ttk.Label(self._frm_params, text="(aucun paramètre)",
                      foreground=_INK_DIM,
                      font=("Arial", 9, "italic")).pack()
            return

        # Récupération des métadonnées pour trouver le VRAI index physique
        model_name = self._cb_model.get()
        params_meta = []
        if model_name in self._model_map and self._tables:
            mid, cat = self._model_map[model_name]
            try:
                params_meta = self._tables.params_of(mid, cat)
            except Exception:
                pass

        for pi, (pname, pval) in enumerate(params.items()):
            pmin, pmax = _param_range(pname, pval)
            pval_c = max(pmin, min(pmax, float(pval)))

            # Trouver l'index physique exact (pour le binaire et le hardware)
            true_idx = pi
            for i, pm in enumerate(params_meta):
                if pm["name"] == pname:
                    true_idx = i
                    break

            # Label du nom du paramètre (ex: TIME)
            tk.Label(self._frm_params, text=pname, bg=_BG, fg=_INK,
                     font=("Arial", 8), width=13, anchor="w"
                     ).grid(row=pi, column=0, sticky="w", pady=2)

            # Variable dynamique pour afficher la valeur en temps réel
            v_disp = tk.StringVar(value=f"{pval_c:.0f}")
            
            # Label d'affichage de la valeur numérique à droite du slider
            tk.Label(self._frm_params, textvariable=v_disp, bg=_BG, fg=_INK,
                     font=("Courier New", 8), width=6, anchor="e"
                     ).grid(row=pi, column=2, sticky="e", padx=(4, 0))

            sc = ttk.Scale(self._frm_params, from_=pmin, to=pmax,
                           orient="horizontal", length=200, value=pval_c)
            sc.grid(row=pi, column=1, sticky="ew", padx=4, pady=2)
            self._frm_params.columnconfigure(1, weight=1)

            # --- Utiliser true_idx (mémoire) et pi (grille UI) ---
            def _on_slider_move(e, pn=pname, vd=v_disp, ti=true_idx):
                # On force l'arrondi à l'entier le plus proche !
                val = float(round(float(e.widget.get())))
                vd.set(f"{val:.0f}")
                self._sync_param_value(pn, val, ti)

            sc.bind("<B1-Motion>", _on_slider_move)  # Pendant le glissement de la souris
            sc.bind("<Motion>", _on_slider_move)     # Au survol/mouvement
            
            sc.bind("<ButtonRelease-1>",
                    lambda e, ri=pi, ti=true_idx, pn=pname, vd=v_disp:
                    self._on_release(e.widget, ri, ti, pn, vd))

            self._sliders.append((sc, pi))

    def _on_save(self):
        """Persiste le preset courant dans slot 1-A via push_preset."""
        model_name = self._cb_model.get() or "preset"
        self._v_status.set("⏳ Sauvegarde…")
        self._btn_save.configure(state="disabled")
        import threading
        threading.Thread(
            target=self._push_full_preset,
            args=(model_name, None, None),
            daemon=True).start()


    # ── Positionnement ─────────────────────────────────────────────────────

    def _place_near_parent(self, parent):
        """Centre la popup sur l'écran comme les autres fenêtres."""
        self.update_idletasks()
        w  = self.winfo_reqwidth()  or 340
        h  = self.winfo_reqheight() or 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Catalogue des modèles ──────────────────────────────────────────────

    def _get_models(self, slot_name: str):
        """Retourne (liste triee des noms, {nom: (mid, cat)}).

        Utilise Tables.models_for_slot() pour un filtrage exact firmware.
        Avant: SLOT_ACCEPTS + by_key -> trop de modeles (ex WAH=26 vs 6).
        Avec le champ slots dans le JSON: comptes exacts par slot.
        """
        names, mapping = [], {}
        if not self._tables:
            return names, mapping
        try:
            if slot_name == "CAB":
                for c in self._tables.cabs:
                    if not c.get("user_slot"):
                        n = c["name"]
                        names.append(n)
                        mapping[n] = (c["model_id"], 10)
            elif hasattr(self._tables, "models_for_slot"):
                # Filtrage exact firmware via champ slots du JSON
                for m, cat in self._tables.models_for_slot(slot_name):
                    n = m.get("name", "")
                    if n and n not in mapping:
                        names.append(n)
                        mapping[n] = (m["id"], cat)
            else:
                # Fallback legacy: by_key + SLOT_ACCEPTS
                cats = SLOT_ACCEPTS.get(slot_name, [])
                seen = set()
                for (mid, cat), m in self._tables.by_key.items():
                    if cat in cats:
                        n = m.get("name", "")
                        if n and n not in seen:
                            seen.add(n)
                            names.append(n)
                            mapping[n] = (mid, cat)
        except Exception:
            pass
        return sorted(names), mapping

    def _on_model_change(self, slot_name: str):
        """Change le modèle du slot, met à jour le prst et push."""
        import struct
        name = self._cb_model.get()
        if name not in self._model_map:
            return
        mid, cat = self._model_map[name]

        # Mettre à jour le nom du modèle dans l'objet local du slot
        self._slot["model"] = name

        # Mettre à jour les bytes du prst en mémoire
        if self._prst and self._rec0 is not None:
            blk = self._rec0 + self._k * 72
            struct.pack_into("<H", self._prst, blk + 8,  mid)
            self._prst[blk + 11] = cat
            # Recalcul checksum
            try:
                from gp180lib import checksum as _cksum
                struct.pack_into(">H", self._prst, len(self._prst) - 2,
                                 _cksum(self._prst))
            except Exception:
                pass

        # Sauvegarder les valeurs ACTUELLES des sliders avant de reconstruire
        current_values = {}
        if self._frm_params:
            try:
                rows = self._frm_params.grid_size()[1]
                for row in range(rows):
                    lbl = self._frm_params.grid_slaves(row=row, column=0)
                    sc  = self._frm_params.grid_slaves(row=row, column=1)
                    if lbl and sc:
                        current_values[lbl[0].cget("text")] = float(sc[0].get())
            except Exception:
                pass

        # Construire les params du nouveau modèle
        new_params = {}
        try:
            params_meta = self._tables.params_of(mid, cat)
            for p in params_meta:
                n = p["name"]
                new_params[n] = (current_values[n]
                                 if n in current_values
                                 else float(p.get("default", 0)))
        except Exception:
            pass

        if new_params:
            self._slot["params"] = new_params
            self._build_params(new_params)
            self.update_idletasks()

        # Synchroniser et rafraîchir l'application principale immédiatement
        try:
            if hasattr(self.master, "_gen") and hasattr(self.master.presets, "_sel") and hasattr(self.master, "_show_chain"):
                sel = self.master.presets._sel
                if 0 <= sel < len(self.master._gen):
                    gen_item = self.master._gen[sel]
                    slot_key = self._slot.get("slot")
                    if "modules" in gen_item and slot_key in gen_item["modules"]:
                        gen_item["modules"][slot_key]["model"] = name
                        gen_item["modules"][slot_key]["params"] = new_params
                    modules = gen_item.get("modules")
                    title = gen_item.get("name", "")
                    self.master._show_chain(modules, title=title)
        except Exception:
            pass

        # Live preview : effectChange + params uniquement
        self._dirty = True
        self._v_status.set(f"⏳ {name}…")
        self.update_idletasks()
        import threading
        threading.Thread(target=self._live_preview_model,
                         args=(name, mid, cat, new_params),
                         daemon=True).start()

    def _live_preview_model(self, model_name: str, mid: int, cat: int,
                             params: dict):
        """Live preview sans write_preset : effectChange + params → zéro flicker.

        Séquence (phash Bug #80 / Bug #90) :
          1. send_effect_change → device affiche le nouveau modèle IMMÉDIATEMENT
          2. 400ms settle        → device charge l'algorithme
          3. send_param_update × N (40ms entre chaque) → params par défaut
          4. re-send param[0]   → Bug #80 : le device avale le 1er param

        AudioWakeKeepAlive peut rester active : chaque SysEx est independant
        (pas de séquence multi-chunk comme write_preset). Collisions benignes.

        Pour persister les changements → bouton Save → _push_full_preset.
        """
        if not self._usb:
            self.after(0, lambda: self._v_status.set("⚫ GP-180 non connecté"))
            return

        import time

        try:
            # ── ÉTAPE 1 : ouvrir le contexte d'édition ─────────────────────
            if hasattr(self._usb, "send_effect_change"):
                self._usb.send_effect_change(self._k, mid, cat)
            else:
                self.after(0, lambda: self._v_status.set(
                    "⚫ send_effect_change indisponible (mettre à jour gp180_usb.py)"))
                return

            # ── ÉTAPE 2 : settle 400ms ─────────────────────────────────────
            time.sleep(0.4)

            # ── ÉTAPE 3 : params par défaut (40ms entre chaque) ───────────
            params_list = list(params.items())
            for idx, (pname, pval) in enumerate(params_list):
                if not self._usb:
                    return
                self._usb.send_param_update(
                    self._k, idx, float(pval),
                    prst_data=self._prst, rec0=self._rec0)
                time.sleep(0.04)  # 40ms — phash: jamais < 19ms entre 2 params

            # ── ÉTAPE 4 : re-send param[0] (Bug #80) ──────────────────────
            # Le device "avale" le 1er param pour ouvrir le contexte d'édition
            # → le re-envoyer en dernier garantit qu'il est bien appliqué.
            if params_list and self._usb:
                first_val = float(params_list[0][1])
                self._usb.send_param_update(
                    self._k, 0, first_val,
                    prst_data=self._prst, rec0=self._rec0)

            self.after(0, lambda: self._v_status.set(
                f"✅ {model_name}  (💾 non sauvegardé)"))

        except Exception as ex:
            self.after(0, lambda: self._v_status.set(f"⚠️ {ex}"))


    def _push_full_preset(self, model_name: str, mid: int = None, cat: int = None):
        """Push le preset complet via push_preset en recréant le binaire depuis la mémoire globale."""
        
        # 1. On vérifie d'abord si l'USB est là AVANT de poser le verrou
        if not self._usb:
            self.after(0, lambda: self._v_status.set("⚫ Pas de preset ou USB"))
            return

        # --- NOUVEAU : On pose le verrou sur l'application mère ---
        if hasattr(self.master, "_usb_busy"):
            self.master._usb_busy = True
            
        # Pause AudioWakeKeepAlive
        wake = getattr(self.master, "_audio_wake", None)
        wake_was_running = wake is not None and getattr(wake, "_running", False)
        if wake_was_running:
            wake.stop()

        try:
            import time
            # ÉTAPE 1 : effectChange → ouvre le contexte d'édition immédiatement si demandé
            if mid is not None and cat is not None and hasattr(self._usb, "send_effect_change"):
                self._usb.send_effect_change(self._k, mid, cat)
                time.sleep(0.4)  # settle : le device charge l'algorithme (~400ms)

            # ── LA CORRECTION EST ICI : Reconstruction totale du binaire ──
            # On fusionne TOUTE la mémoire de l'application avec le fichier original.
            import os
            import json
            from gp180lib import decode_prst, encode_prst
            from gp180_agent import decoded_to_spec
            
            if not self._prst_path or not self._tables:
                raise Exception("Chemin du preset ou tables manquantes")

            # 1. Lire le preset original sur le disque pour garder ses bases (patch_vol, chain_order)
            decoded = decode_prst(self._prst_path, self._tables)
            full_spec = decoded_to_spec(decoded)

            # 2. Injecter TOUTES les modifications de TOUS les effets depuis la mémoire de l'app
            if hasattr(self.master, "_gen") and hasattr(self.master.presets, "_sel"):
                sel = self.master.presets._sel
                if 0 <= sel < len(self.master._gen):
                    live_modules = self.master._gen[sel].get("modules")
                    if live_modules:
                        full_spec["modules"] = live_modules

            # 3. Retrouver le template original pour l'encodage
            try:
                from gp180_agent import resource_path
                tpl_path = resource_path("template.prst")
            except ImportError:
                tpl_path = "template.prst"

            # 4. Générer un nouveau binaire propre et parfait !
            new_raw, _ = encode_prst(full_spec, self._tables, template=tpl_path)
            self._prst = bytearray(new_raw) # On met à jour le buffer local

            # ÉTAPE 2 : push_preset sur le hardware avec le binaire parfait
            self._usb.push_preset(1, "A", bytes(self._prst), delay_after_write=0.3)
            
            # ÉTAPE 3 : Export local
            file_msg = ""
            try:
                with open(self._prst_path, "wb") as f:
                    f.write(self._prst)
                
                json_path = self._prst_path[:-5] + ".json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(full_spec, f, indent=1, ensure_ascii=False)
                    
                file_msg = f" & {os.path.basename(self._prst_path)} (+ json) mis à jour"
            except Exception as e:
                file_msg = f" (⚠️ Erreur sauvegarde : {e})"

            self._dirty = False
            self.after(0, lambda msg=file_msg: self._v_status.set(f"✅ Sauvegardé → slot 1-A{msg}"))
            self.after(0, lambda: self._btn_save.configure(state="normal"))
            
        except Exception as ex:
            self.after(0, lambda: self._v_status.set(f"❌ {ex}"))
            
        finally:
            # --- NOUVEAU : On retire le verrou ---
            if hasattr(self.master, "_usb_busy"):
                self.master._usb_busy = False
                
            # --- NOUVEAU : Le code manquant pour relancer l'audio ---
            if wake_was_running:
                restart = getattr(self.master, "_start_audio_wake", None)
                if restart:
                    self.after(500, restart)

    # ── Callbacks ──────────────────────────────────────────────────────────

    def _on_toggle(self):
        """Bypass ON/OFF via send_bypass."""
        active = self._v_on.get()
        
        # 1. Mettre à jour l'état local du slot dans la popup
        self._slot["on"] = active

        # 2. Mettre à jour la mémoire de l'application principale et rafraîchir le rack
        try:
            if hasattr(self.master, "_gen") and hasattr(self.master.presets, "_sel") and hasattr(self.master, "_show_chain"):
                sel = self.master.presets._sel
                if 0 <= sel < len(self.master._gen):
                    gen_item = self.master._gen[sel]
                    slot_key = self._slot.get("slot")
                    if "modules" in gen_item and slot_key in gen_item["modules"]:
                        gen_item["modules"][slot_key]["on"] = active
                    modules = gen_item.get("modules")
                    title = gen_item.get("name", "")
                    self.master._show_chain(modules, title=title)
        except Exception:
            pass

        # 3. Envoyer la commande au matériel via USB
        if self._usb and hasattr(self._usb, "send_bypass"):
            ok = self._usb.send_bypass(self._k, active)
            self._v_status.set(
                f"{'🟢' if active else '⭕'} {'Actif' if active else 'Bypass'}"
                + ("" if ok else " — ❌"))
        else:
            self._v_status.set("⚫ GP-180 non connecté")

    def _on_release(self, widget, row_idx: int, param_idx: int, param_name: str, v_disp):
        """Envoie la nouvelle valeur au GP-180 et synchronise les mémoires."""
        # On force l'arrondi à l'entier le plus proche !
        val = float(round(float(widget.get())))
        v_disp.set(f"{val:.0f}")

        # Synchronisation immédiate avec l'index physique exact
        self._sync_param_value(param_name, val, param_idx)

        if self._usb and hasattr(self._usb, "send_param_update"):
            ok = self._usb.send_param_update(
                self._k, param_idx, val,
                prst_data=self._prst, rec0=self._rec0)
            try:
                pname_lbl = widget.master.grid_slaves(row=row_idx, column=0)[0].cget('text')
            except Exception:
                pname_lbl = param_name
            self._v_status.set(f"{'✅' if ok else '❌'} {pname_lbl} = {val:.0f}")
        else:
            self._v_status.set("⚫ GP-180 non connecté")

    # ── USB ────────────────────────────────────────────────────────────────

    def _connect_usb(self):
        if not _USB_OK:
            self._v_status.set("⚫ gp180_usb indisponible")
            return
        dev = GP180USB(verbose=False)
        if dev.connect():
            self._usb = dev
            self._v_status.set("🔵 GP-180 connecté")
        else:
            self._v_status.set("⚫ GP-180 non détecté")

    # ── Fermeture ──────────────────────────────────────────────────────────

    def _on_destroy(self):
        """Appelé à la fermeture de la popup : rafraîchit l'interface principale en conservant le focus."""
        try:
            if hasattr(self.master, "_gen") and hasattr(self.master.presets, "_sel") and hasattr(self.master, "_show_chain"):
                sel = self.master.presets._sel
                if 0 <= sel < len(self.master._gen):
                    gen_item = self.master._gen[sel]
                    modules = gen_item.get("modules")
                    title = gen_item.get("name", "")
                    
                    # On appelle _show_chain en verrouillant l'index exact de notre slot (self._k)
                    self.master._show_chain(modules, title=title, select_idx=self._k)
        except Exception:
            pass

        if self._usb:
            try:
                self._usb.disconnect()
            except Exception:
                pass
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                pass
        self.destroy()
