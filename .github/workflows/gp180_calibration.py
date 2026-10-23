# -*- coding: utf-8 -*-
"""
GP-180 Studio -- Fenetre de calibration volume LUFS.

Module autonome : ouvre une tk.Toplevel independante.
La seule modification dans gp180_studio.py est :
    1. from gp180_calibration import CalibrationWindow
    2. un bouton qui appelle CalibrationWindow(self, self.cfg)

Workflow utilisateur :
    1. Charger un .prst
    2. Selectionner l'entree audio (interface connectee au GP-180)
    3. Cliquer Mesurer, jouer quelques secondes (powerchord repete)
    4. L'app affiche le delta LUFS vs cible + suggestion de patch_vol
    5. Ajuster le Spinbox si besoin, re-mesurer
    6. Cliquer Appliquer --> .prst reecrit avec checksum recalcule
"""

import os
import struct
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from gp180_lufs import LUFSEngine, list_input_devices, DEPS_OK, DEPS_MSG
except ImportError:
    DEPS_OK  = False
    DEPS_MSG = "gp180_lufs.py introuvable."
    LUFSEngine = None
    def list_input_devices(): return []

# ── constantes ────────────────────────────────────────────────────────────────

OFF_PATCH_VOL  = 0x38    # byte 56 : volume global du preset
PRST_SIZE      = 1224
CS_OFFSET      = 1222    # offset uint16 LE du checksum
CS_DATA_LEN    = 1222    # nombre de bytes couverts par le checksum

# Cibles LUFS par categorie (ajustables apres calibration reelle)
TARGETS = {
    "Clean / Rythm"    : -18.0,
    "Lead / Solo"      : -16.0,
    "High Gain / Disto": -20.0,
}

# Ratio empirique de depart : combien de LUFS par unite de patch_vol
# A affiner apres premieres mesures reelles sur le GP-180
# Note : ce ratio varie selon l'ampli -- c'est une estimation initiale
LUFS_PER_UNIT = 0.4

# Tolerance : ecart acceptable avant de proposer "Appliquer"
TOLERANCE_DB  = 1.0


# ── checksum ──────────────────────────────────────────────────────────────────

def _compute_checksum(data: bytearray) -> int:
    """Somme des CS_DATA_LEN premiers bytes, uint16."""
    return sum(data[:CS_DATA_LEN]) & 0xFFFF


def _write_preset(path: str, data: bytearray, new_vol: int) -> None:
    """Ecrit le patch_vol et recalcule le checksum, puis sauvegarde."""
    data[OFF_PATCH_VOL] = max(0, min(100, new_vol))
    cs = _compute_checksum(data)
    struct.pack_into(">H", data, CS_OFFSET, cs)
    with open(path, "wb") as f:
        f.write(data)


# ── fenetre principale ─────────────────────────────────────────────────────────

class CalibrationWindow(tk.Toplevel):
    """
    Fenetre de calibration volume LUFS.
    S'instancie avec : CalibrationWindow(parent, cfg)
    """

    POLL_MS  = 150    # periode de rafraichissement de l'affichage Tk

    def __init__(self, parent, cfg=None):
        super().__init__(parent)
        self.title("GP-180 Studio  —  Calibration Volume LUFS")
        self.resizable(False, False)
        self.grab_set()

        self._cfg     = cfg or {}
        self._engine  = None
        self._running = False

        # Preset charge
        self._prst_path = None
        self._prst_data = None

        # Variables Tkinter
        self._v_prst   = tk.StringVar(value="(aucun fichier charge)")
        self._v_vol    = tk.IntVar(value=50)
        self._v_target = tk.StringVar(value=list(TARGETS)[0])
        self._v_mom    = tk.StringVar(value="    ---")
        self._v_st     = tk.StringVar(value="    ---")
        self._v_itg    = tk.StringVar(value="    ---")
        self._v_delta  = tk.StringVar(value="    ---")
        self._v_hint   = tk.StringVar(value="")
        self._v_status = tk.StringVar(value="Pret.")

        # Dernieres valeurs LUFS (ecrites par le thread audio, lues par _poll)
        self._last = (None, None, None)

        self._build_ui()
        self._refresh_devices()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── construction UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        P = 12
        self.columnconfigure(0, weight=1)

        # ── Preset ──────────────────────────────────────────────────────────
        g = ttk.LabelFrame(self, text=" 1. Preset .prst ", padding=P)
        g.grid(row=0, column=0, sticky="ew", padx=P, pady=(P, 4))
        g.columnconfigure(0, weight=1)

        ttk.Label(g, textvariable=self._v_prst,
                  anchor="w", width=42).grid(row=0, column=0, sticky="w")
        ttk.Button(g, text="📂  Ouvrir…",
                   command=self._open_prst).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(g, text="patch_vol actuel :").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        self._spn = ttk.Spinbox(g, from_=0, to=100, width=7,
                                 textvariable=self._v_vol)
        self._spn.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        # ── Entree audio ─────────────────────────────────────────────────────
        g2 = ttk.LabelFrame(self, text=" 2. Entree audio ", padding=P)
        g2.grid(row=1, column=0, sticky="ew", padx=P, pady=4)
        g2.columnconfigure(0, weight=1)

        self._cb_dev = ttk.Combobox(g2, state="readonly", width=40)
        self._cb_dev.grid(row=0, column=0, sticky="ew")
        ttk.Button(g2, text="↺", width=3,
                   command=self._refresh_devices).grid(row=0, column=1, padx=(6, 0))

        # ── Cible LUFS ───────────────────────────────────────────────────────
        g3 = ttk.LabelFrame(self, text=" 3. Cible LUFS ", padding=P)
        g3.grid(row=2, column=0, sticky="ew", padx=P, pady=4)

        self._cb_tgt = ttk.Combobox(g3, state="readonly",
                                     values=list(TARGETS),
                                     textvariable=self._v_target, width=24)
        self._cb_tgt.grid(row=0, column=0, sticky="w")
        self._cb_tgt.current(0)
        self._cb_tgt.bind("<<ComboboxSelected>>", lambda _: self._refresh_tgt_lbl())

        self._lbl_tgt_val = ttk.Label(g3, text="",
                                       font=("Courier", 12, "bold"),
                                       foreground="#003399")
        self._lbl_tgt_val.grid(row=0, column=1, padx=(16, 0))
        self._refresh_tgt_lbl()

        # ── Mesures LUFS ─────────────────────────────────────────────────────
        g4 = ttk.LabelFrame(self, text=" 4. Mesure LUFS (EBU R128) ", padding=P)
        g4.grid(row=3, column=0, sticky="ew", padx=P, pady=4)

        rows_m = [
            ("Momentary   (400 ms)", self._v_mom, "gray50"),
            ("Short-term      (3 s)", self._v_st,  "gray30"),
            ("Integre   (total)",     self._v_itg, "#003399"),
        ]
        for i, (lbl, var, col) in enumerate(rows_m):
            ttk.Label(g4, text=lbl, anchor="w",
                      width=24).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(g4, textvariable=var,
                      font=("Courier", 16, "bold"),
                      foreground=col, width=9, anchor="e").grid(
                row=i, column=1, sticky="e")
            ttk.Label(g4, text="LUFS").grid(row=i, column=2, padx=(4, 0))

        ttk.Separator(g4).grid(row=3, column=0, columnspan=3,
                                sticky="ew", pady=8)

        ttk.Label(g4, text="Ecart vs cible", anchor="w",
                  width=24).grid(row=4, column=0, sticky="w")
        self._lbl_delta = ttk.Label(g4, textvariable=self._v_delta,
                                     font=("Courier", 16, "bold"),
                                     width=9, anchor="e")
        self._lbl_delta.grid(row=4, column=1, sticky="e")
        ttk.Label(g4, text="dB").grid(row=4, column=2, padx=(4, 0))

        self._lbl_hint = ttk.Label(g4, textvariable=self._v_hint,
                                    font=("Arial", 10, "italic"),
                                    wraplength=380, justify="center")
        self._lbl_hint.grid(row=5, column=0, columnspan=3, pady=(10, 2))

        # ── Boutons ──────────────────────────────────────────────────────────
        frm_btn = ttk.Frame(self, padding=(P, 6))
        frm_btn.grid(row=4, column=0, pady=4)

        self._btn_measure = ttk.Button(frm_btn, text="▶  Mesurer",
                                        width=14, command=self._toggle_measure)
        self._btn_measure.grid(row=0, column=0, padx=5)

        ttk.Button(frm_btn, text="⟳  Reset",
                   width=12, command=self._reset_measure).grid(row=0, column=1, padx=5)

        self._btn_apply = ttk.Button(frm_btn, text="✔  Appliquer",
                                      width=14, command=self._apply,
                                      state="disabled")
        self._btn_apply.grid(row=0, column=2, padx=5)

        # ── Barre de statut ──────────────────────────────────────────────────
        ttk.Label(self, textvariable=self._v_status,
                  font=("Arial", 9, "italic"),
                  foreground="gray50").grid(row=5, column=0,
                                            padx=P, pady=(2, P), sticky="w")

    # ── peripheriques audio ────────────────────────────────────────────────────

    def _refresh_devices(self):
        self._devices = list_input_devices()
        self._cb_dev["values"] = [f"[{i}]  {n}" for i, n in self._devices]
        if self._devices:
            self._cb_dev.current(0)

    def _refresh_tgt_lbl(self):
        t = TARGETS[self._v_target.get()]
        self._lbl_tgt_val.config(text=f"{t:+.1f} LUFS")

    # ── chargement preset ──────────────────────────────────────────────────────

    def _open_prst(self):
        path = filedialog.askopenfilename(
            title="Ouvrir preset GP-180",
            filetypes=[("GP-180 preset", "*.prst"), ("Tous", "*.*")],
        )
        if not path:
            return
        try:
            raw = open(path, "rb").read()
        except OSError as e:
            messagebox.showerror("Erreur lecture", str(e), parent=self)
            return
        if len(raw) != PRST_SIZE:
            messagebox.showerror(
                "Fichier invalide",
                f"Taille inattendue : {len(raw)} bytes (attendu {PRST_SIZE}).",
                parent=self)
            return

        self._prst_path = path
        self._prst_data = bytearray(raw)
        vol = raw[OFF_PATCH_VOL]
        self._v_vol.set(vol)
        self._v_prst.set(os.path.basename(path))
        self._status(f"Charge : {os.path.basename(path)}  |  patch_vol = {vol}")

    # ── mesure LUFS ────────────────────────────────────────────────────────────

    def _toggle_measure(self):
        if self._running:
            self._stop_measure()
        else:
            self._start_measure()

    def _start_measure(self):
        if not DEPS_OK:
            messagebox.showerror(
                "Dependances manquantes",
                f"{DEPS_MSG}\n\nInstalle avec :\n"
                "pip install sounddevice pyloudnorm",
                parent=self)
            return

        sel = self._cb_dev.current()
        if sel < 0 or sel >= len(self._devices):
            messagebox.showerror("Erreur",
                                  "Selectionne un peripherique audio.", parent=self)
            return

        dev_idx = self._devices[sel][0]
        try:
            self._engine = LUFSEngine(callback=self._on_lufs)
            self._engine.start(device=dev_idx)
            self._running = True
            self._btn_measure.config(text="⏹  Stop")
            self._status("Mesure en cours — joue quelques secondes…")
        except Exception as e:
            messagebox.showerror("Erreur audio", str(e), parent=self)

    def _stop_measure(self):
        if self._engine:
            self._engine.stop()
            self._engine = None
        self._running = False
        self._btn_measure.config(text="▶  Mesurer")
        self._status("Mesure arretee.")

    def _reset_measure(self):
        if self._engine:
            self._engine.reset()
        self._last = (None, None, None)
        for v in (self._v_mom, self._v_st, self._v_itg, self._v_delta):
            v.set("    ---")
        self._v_hint.set("")
        self._btn_apply.config(state="disabled")
        self._status("Reset — pret pour une nouvelle mesure.")

    # ── callback thread audio + boucle d'affichage ────────────────────────────

    def _on_lufs(self, momentary, short_term, integrated):
        """Stockage thread-safe -- l'affichage se fait dans _poll (thread Tk)."""
        self._last = (momentary, short_term, integrated)

    def _poll(self):
        """Boucle Tkinter : lit _last et met a jour l'UI toutes les POLL_MS."""
        m, st, itg = self._last
        if m is not None or st is not None or itg is not None:
            self._update_display(m, st, itg)
        self.after(self.POLL_MS, self._poll)

    def _update_display(self, m, st, itg):
        def fmt(v):
            return f"{v:+7.1f}" if v is not None else "    ---"

        self._v_mom.set(fmt(m))
        self._v_st.set(fmt(st))
        self._v_itg.set(fmt(itg))

        if itg is not None:
            target = TARGETS[self._v_target.get()]
            delta  = itg - target
            self._v_delta.set(f"{delta:+7.1f}")

            if abs(delta) <= TOLERANCE_DB:
                # ── Volume OK ──
                self._lbl_delta.config(foreground="#1B5E20")
                self._v_hint.set("✅  Volume OK — tu peux cliquer Appliquer.")
                self._btn_apply.config(
                    state="normal" if self._prst_path else "disabled")

            else:
                # ── Suggestion de correction ──
                # Ratio LUFS_PER_UNIT : estimation initiale, a affiner
                # apres premieres mesures reelles sur le setup
                units = int(round(abs(delta) / LUFS_PER_UNIT))
                cur   = self._v_vol.get()
                # delta > 0 : trop fort  → baisser patch_vol
                # delta < 0 : trop faible → monter patch_vol
                new_v = max(0, min(100, cur + (-units if delta > 0 else units)))

                direction = "↓ Baisser" if delta > 0 else "↑ Monter"
                color     = "#E65100" if abs(delta) <= 4.0 else "#B71C1C"
                self._lbl_delta.config(foreground=color)
                self._v_hint.set(
                    f"{direction} patch_vol d'environ {units} unite(s)  →  essaie {new_v}\n"
                    f"(ratio {LUFS_PER_UNIT} dB/unite — estimation initiale, a affiner)"
                )
                self._btn_apply.config(state="disabled")
        else:
            self._v_delta.set("    ---")
            self._v_hint.set("")

    # ── application de la correction ──────────────────────────────────────────

    def _apply(self):
        if not self._prst_path or self._prst_data is None:
            messagebox.showerror("Erreur", "Aucun preset charge.", parent=self)
            return

        new_vol = max(0, min(100, self._v_vol.get()))
        old_vol = self._prst_data[OFF_PATCH_VOL]

        try:
            _write_preset(self._prst_path, self._prst_data, new_vol)
        except OSError as e:
            messagebox.showerror("Erreur ecriture", str(e), parent=self)
            return

        self._status(
            f"✅  patch_vol {old_vol} → {new_vol}  "
            f"sauvegarde dans {os.path.basename(self._prst_path)}"
        )
        messagebox.showinfo(
            "Sauvegarde OK",
            f"patch_vol = {new_vol} ecrit dans :\n{os.path.basename(self._prst_path)}\n\n"
            f"Recharge le preset sur ton GP-180 et re-mesure pour confirmer.",
            parent=self)
        self._btn_apply.config(state="disabled")
        self._reset_measure()

    # ── utilitaires ───────────────────────────────────────────────────────────

    def _status(self, msg):
        self._v_status.set(msg)

    def _on_close(self):
        self._stop_measure()
        self.destroy()
