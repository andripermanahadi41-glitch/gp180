#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GP-180 Studio -- Systeme de design "Retro-Future Hardware".

Ce module ne contient AUCUNE logique metier. Il expose :

  * les jetons de design (couleurs, espacements, rayons, typo)
  * des utilitaires couleur (melange, eclaircissement, rampes de degrade)
  * apply_theme(root)  qui recable entierement le theme ttk

Zero dependance externe : ni PIL, ni sv_ttk, ni ttkbootstrap.
Tout est calcule a la main et dessine par Tkinter.

Import type :
    from gp180_theme import TOK, CAT, apply_theme, mix, ramp
"""

import math

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError:                                    # pragma: no cover
    tk = ttk = tkfont = None


# =============================================================================
#  1. UTILITAIRES COULEUR
# =============================================================================

def _rgb(h):
    """'#1a9fc7' -> (26, 159, 199). Accepte aussi la forme courte '#abc'."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        raise ValueError("couleur invalide: %r" % h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex(t):
    """(26, 159, 199) -> '#1a9fc7'. Clampe dans 0..255."""
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in t)


def mix(a, b, t):
    """Melange lineaire entre deux couleurs. t=0 -> a, t=1 -> b."""
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3)))


def lighten(c, t):
    """Eclaircit vers le blanc."""
    return mix(c, "#ffffff", t)


def darken(c, t):
    """Assombrit vers le noir."""
    return mix(c, "#000000", t)


def ramp(a, b, n):
    """Liste de n couleurs de a a b. Sert aux degrades dessines au Canvas."""
    if n <= 1:
        return [a]
    return [mix(a, b, i / float(n - 1)) for i in range(n)]


def luma(c):
    """Luminance percue 0..255. Sert a choisir un texte lisible sur un fond."""
    r, g, b = _rgb(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# =============================================================================
#  2. JETONS DE DESIGN
# =============================================================================
#
#  Concept : materiel audio numerique de rack, annees 90-2000, relu par un
#  oeil moderne. Chassis sombre, serigraphie fine, LEDs, trace de signal cyan.
#
#  Regle de lecture des noms :
#     bg_*      surfaces de fond, du plus profond au plus haut
#     ink_*     encres (texte), du plus fort au plus faible
#     line_*    filets et bordures
#     acc_*     accent cyan, la seule couleur "vive" de l'interface
#
TOK = {
    # -- chassis ------------------------------------------------------------
    "bg_deep":      "#141414",   # bord de fenetre, zones creusees
    "bg_top":       "#1a1a1a",   # haut du degrade de fond
    "bg_bot":       "#2d2d2d",   # bas du degrade de fond
    "bg_panel":     "#212121",   # panneaux (sidebar, footer)
    "bg_panel_hi":  "#282828",   # panneau survole
    "bg_field":     "#171717",   # champs de saisie, creux
    "bg_rail":      "#1e1e1e",   # rail de la grille de slots

    # -- encres -------------------------------------------------------------
    "ink":          "#e0e8f0",   # texte principal
    "ink_dim":      "#8fa0b0",   # texte secondaire
    "ink_label":    "#6b8fa0",   # serigraphie : petits labels majuscules
    "ink_ghost":    "#4a5a66",   # desactive, placeholders

    # -- filets -------------------------------------------------------------
    "line":         "#333a3f",   # filet standard
    "line_soft":    "#2a2f33",   # separateur discret
    "line_strong":  "#48545c",   # bordure appuyee / focus au repos
    "bevel":        "#3d4750",   # liseré haut : la lumiere qui accroche l'arete

    # -- accent -------------------------------------------------------------
    "acc":          "#1a9fc7",   # cyan primaire
    "acc_hi":       "#3fc4e8",   # cyan survole
    "acc_lo":       "#12708d",   # cyan enfonce
    "acc_ink":      "#04222c",   # texte SUR le cyan

    # -- etats --------------------------------------------------------------
    "ok":           "#5dcaa5",
    "warn":         "#efa927",
    "err":          "#e2564a",
    "led_off":      "#3a2222",   # LED eteinte : rouge tres sombre, pas gris

    # -- geometrie ----------------------------------------------------------
    "r_card":       12,          # rayon des cartes de slot
    "r_ctl":        8,           # rayon des controles
    "r_pill":       999,         # pastilles
    "pad_xs":       4,
    "pad_sm":       8,
    "pad_md":       14,
    "pad_lg":       22,
    "pad_xl":       32,
    "gap":          18,          # gouttiere de la grille de slots
    "h_ctl":        32,          # hauteur standard d'un controle
    "card_w":       206,         # carte de slot, mode large (repli multi-rangs)
    "card_h":       122,
    "card_wc":      126,         # carte de slot, mode compact : les 11 modules
    "card_hc":      120,         # tiennent sur UNE ligne, comme la vraie chaine
    "insp_h":       150,         # hauteur de reference de l'inspecteur
    "sidebar_w":    228,
}


# -----------------------------------------------------------------------------
#  Categories de modules
# -----------------------------------------------------------------------------
#  Les 11 modules du GP-180 sont regroupes en trois familles. La couleur n'est
#  pas decorative : elle dit ou on se trouve dans la chaine de signal.
#
#     GEN  ce qui fabrique le son     PRE  DST  AMP
#     CAB  ce qui le met en forme     NR   CAB  EQ
#     FX   ce qui le colore           WAH  MOD  DLY  RVB  VOL
#
CAT = {
    "GEN": {
        "dark":   "#1a4d6d",    # bas du degrade de carte
        "light":  "#a8d5f7",    # encre / liseré de la famille
        "tint":   "#12313f",    # fond de carte au repos (haut du degrade)
        "glow":   "#4aa8dd",
    },
    "CAB": {
        "dark":   "#1f4d1f",
        "light":  "#c8e0a8",
        "tint":   "#16301a",
        "glow":   "#7fb84f",
    },
    "FX": {
        "dark":   "#4d1f3f",
        "light":  "#e0b8d8",
        "tint":   "#33162a",
        "glow":   "#c06aa8",
    },
}

# Rattachement module -> famille. Aligne sur gp180lib.MODULES.
SLOT_CAT = {
    "PRE": "GEN", "DST": "GEN", "AMP": "GEN",
    "NR":  "CAB", "CAB": "CAB", "EQ":  "CAB",
    "WAH": "FX",  "MOD": "FX",  "DLY": "FX",  "RVB": "FX",  "VOL": "FX",
}

# =============================================================================
#  LIBELLES DE L'INTERFACE GRAPHIQUE
# =============================================================================
#
#  Ces chaines appartiennent a la couche de presentation (noms de modules
#  affiches dans la chaine, etats, messages du rack et de l'inspecteur).
#
#  Elles ne passent PAS par gp180_i18n.py, volontairement : ce module fait
#  partie du moteur et reste inchange. Et gp180_theme n'importe rien du
#  projet, ce qui permet de tester la couche graphique isolement.
#  L'application appelle set_ui_lang() a chaque construction d'interface.
#
UI_LANG = ["fr"]
_LANGS_OK = ("fr", "en", "es")


def set_ui_lang(code):
    """Fixe la langue des libelles graphiques. A appeler depuis l'appli."""
    UI_LANG[0] = code if code in _LANGS_OK else "fr"
    return UI_LANG[0]


_UI = {
    # -- familles de modules
    "fam_GEN":   {"fr": "Generateur", "en": "Generator", "es": "Generador"},
    "fam_CAB":   {"fr": "Cabinet",    "en": "Cabinet",   "es": "Pantalla"},
    "fam_FX":    {"fr": "Effet",      "en": "Effect",    "es": "Efecto"},

    # -- noms des 11 slots, tels qu'affiches sous le nom du modele
    "slot_PRE":  {"fr": "Pre / Comp",  "en": "Pre / Comp",  "es": "Pre / Comp"},
    "slot_WAH":  {"fr": "Wah",         "en": "Wah",         "es": "Wah"},
    "slot_DST":  {"fr": "Drive",       "en": "Drive",       "es": "Drive"},
    "slot_AMP":  {"fr": "Ampli",       "en": "Amp",         "es": "Ampli"},
    "slot_NR":   {"fr": "Noise Gate",  "en": "Noise Gate",  "es": "Noise Gate"},
    "slot_CAB":  {"fr": "Baffle / IR", "en": "Cab / IR",    "es": "Pantalla / IR"},
    "slot_EQ":   {"fr": "Egaliseur",   "en": "Equalizer",   "es": "Ecualizador"},
    "slot_MOD":  {"fr": "Modulation",  "en": "Modulation",  "es": "Modulacion"},
    "slot_DLY":  {"fr": "Delay",       "en": "Delay",       "es": "Delay"},
    "slot_RVB":  {"fr": "Reverbe",     "en": "Reverb",      "es": "Reverb"},
    "slot_VOL":  {"fr": "Volume",      "en": "Volume",      "es": "Volumen"},

    # -- etats et messages du rack
    "active":    {"fr": "actif",  "en": "on",       "es": "activo"},
    "bypass":    {"fr": "bypass", "en": "bypassed", "es": "bypass"},
    "chain_empty": {"fr": "chaine vide", "en": "empty chain",
                    "es": "cadena vacia"},
    "chain_hint":  {"fr": "Decris un son, ou charge un preset.",
                    "en": "Describe a sound, or load a preset.",
                    "es": "Describe un sonido, o carga un preset."},

    # -- inspecteur de module
    "no_module":   {"fr": "aucun module choisi", "en": "no module selected",
                    "es": "ningun modulo elegido"},
    "no_module_hint": {
        "fr": "Clique un module de la chaine pour voir tous ses reglages.",
        "en": "Click a module in the chain to see all of its settings.",
        "es": "Haz clic en un modulo de la cadena para ver todos sus ajustes."},
    "no_params":   {"fr": "Ce module n'expose aucun parametre.",
                    "en": "This module exposes no parameters.",
                    "es": "Este modulo no expone ningun parametro."},
    "no_param_short": {"fr": "aucun parametre", "en": "no parameter",
                       "es": "sin parametro"},
    "module_of":   {"fr": "module %d sur %d", "en": "module %d of %d",
                    "es": "modulo %d de %d"},
}


def TX(key, *args):
    """Libelle graphique traduit dans la langue courante."""
    d = _UI.get(key) or {}
    txt = d.get(UI_LANG[0]) or d.get("fr") or key
    return (txt % args) if args else txt


def slot_name(slot):
    """Nom lisible d'un slot ('AMP' -> 'Ampli' / 'Amp' / 'Ampli')."""
    return TX("slot_" + slot) if ("slot_" + slot) in _UI else slot


def cat_label(cat):
    """Nom de famille ('GEN' -> 'Generateur' / 'Generator' / 'Generador')."""
    return TX("fam_" + cat) if ("fam_" + cat) in _UI else cat


# Conserve pour compatibilite : certains appels historiques lisent SLOT_NAME
# comme un dict. Il reflete la langue au moment de la lecture.
class _SlotNames(dict):
    def get(self, k, default=None):
        return slot_name(k) if ("slot_" + str(k)) in _UI else default

    def __getitem__(self, k):
        return slot_name(k)


SLOT_NAME = _SlotNames()


# Ordre d'affichage = ordre de la chaine de signal, pas l'ordre alphabetique.
SLOT_ORDER = ["PRE", "WAH", "DST", "AMP", "NR", "CAB",
              "EQ", "MOD", "DLY", "RVB", "VOL"]


# Copie de reference des jetons geometriques. La mise a l'echelle repart
# toujours de ces valeurs, jamais du resultat de la passe precedente : sinon
# deux appels a apply_theme() composeraient leurs facteurs.
_TOK_BASE = {k: v for k, v in TOK.items() if isinstance(v, int)}

# Ecran de reference du design : 1600x900 en 100 %.
_REF_W, _REF_H = 1600.0, 900.0


def compute_scale(root):
    """Facteur d'echelle deduit de la resolution reelle de l'ecran.

    Un ecran 2560x1440 doit donner des cartes plus grandes, pas seulement
    plus nombreuses ; un portable 1366x768 doit tout resserrer plutot que
    tronquer. Borne a 0.85-1.30 : au-dela l'interface devient caricaturale.
    """
    try:
        w = float(root.winfo_screenwidth())
        h = float(root.winfo_screenheight())
    except Exception:
        return 1.0
    if w <= 0 or h <= 0:
        return 1.0
    return max(0.85, min(1.30, min(w / _REF_W, h / _REF_H)))


def scale_tokens(s):
    """Applique le facteur aux jetons geometriques, depuis les valeurs de base."""
    for k, base in _TOK_BASE.items():
        if k == "r_pill":                    # pastille : rayon symbolique
            continue
        TOK[k] = max(1, int(round(base * s)))
    return TOK


# =============================================================================
#  3. TYPOGRAPHIE
# =============================================================================
#
#  Trois roles, trois familles.
#
#    display  Bahnschrift Condensed. Livree avec Windows 10/11, etroite,
#             technique, sans personnalite "bureautique". En majuscules
#             interlettrees, elle donne la serigraphie d'un chassis.
#    body     Segoe UI. Neutre, lisible, deja utilisee dans l'appli.
#    data     Cascadia Mono / Consolas. Chiffres a chasse fixe : les valeurs
#             de parametres ne dansent pas quand elles changent.
#
_FAM = {
    "display": ["Bahnschrift Condensed", "Bahnschrift SemiCondensed",
                "Bahnschrift", "Segoe UI Semibold", "DejaVu Sans Condensed",
                "Segoe UI", "Helvetica"],
    "body":    ["Segoe UI", "Inter", "DejaVu Sans", "Helvetica"],
    "data":    ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"],
}

UI_SCALE = [1.0]   # facteur courant, lisible par l'appelant
FONT = {}          # rempli par apply_theme() : FONT["h1"] -> (famille, taille, style)


def _pick(root, names):
    """Premiere famille reellement installee, sinon la derniere de la liste."""
    try:
        have = {f.lower() for f in tkfont.families(root)}
    except Exception:
        return names[-1]
    for n in names:
        if n.lower() in have:
            return n
    return names[-1]


def _build_fonts(root, s=1.0):
    def z(n):
        return max(7, int(round(n * s)))
    d = _pick(root, _FAM["display"])
    b = _pick(root, _FAM["body"])
    m = _pick(root, _FAM["data"])
    FONT.update({
        "family_display": d,
        "family_body":    b,
        "family_data":    m,

        "h1":     (d, z(19), "bold"),     # titre de fenetre / marque
        "h2":     (d, z(13), "bold"),     # titre de section
        "h3":     (b, z(11), "bold"),     # titre de carte
        "body":   (b, z(10), "normal"),
        "small":  (b, z(9), "normal"),
        "label":  (d, z(9), "bold"),     # serigraphie majuscule interlettree
        "micro":  (d, z(8), "bold"),
        "data":   (m, z(9), "normal"),   # valeurs de parametres
        "data_b": (m, z(10), "bold"),     # afficheur principal
        "mono":   (m, z(9), "normal"),   # zones log / resultat
        "micro_mono": (m, z(8), "normal"),
    })
    return FONT


def sil(s, sp=1):
    """Serigraphie : majuscules + interlettrage par espaces fins.

    Tkinter ne sait pas espacer les lettres (pas de letter-spacing), alors on
    insere l'espacement dans la chaine. Reserve aux labels COURTS.
    """
    g = " " * sp
    return g.join(s.upper())


# =============================================================================
#  4. THEME ttk
# =============================================================================

def apply_theme(root, scale=None):
    """Recable le theme ttk sur la palette Retro-Future Hardware.

    scale : facteur d'echelle. None = deduit de la resolution de l'ecran.

    Base sur 'clam', le seul theme ttk integralement recolorable sur les trois
    OS ('vista' et 'aqua' ignorent la plupart des options de couleur).

    Retourne le dict FONT, pour que l'appelant puisse s'en servir.
    """
    if scale is None:
        scale = compute_scale(root)
    scale_tokens(scale)
    _build_fonts(root, scale)
    UI_SCALE[0] = scale
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass

    T = TOK
    root.configure(bg=T["bg_deep"])

    # -- option database : couvre les widgets tk classiques (Text, Menu, ...)
    #
    #  ttk.Style ne touche QUE les widgets ttk. Les widgets Tk classiques
    #  (Listbox, Scale, Text, Menu...) gardent sinon les couleurs systeme --
    #  typiquement un fond blanc, catastrophique sur une interface sombre.
    #  L'option database est le seul moyen de les rattraper globalement.
    #  Attention : elle ne s'applique qu'aux widgets crees APRES cet appel.
    root.option_add("*Font", FONT["body"])
    root.option_add("*Text.background", T["bg_field"])
    root.option_add("*Text.foreground", T["ink"])
    root.option_add("*Text.insertBackground", T["acc"])
    root.option_add("*Text.selectBackground", T["acc_lo"])
    root.option_add("*Text.selectForeground", T["ink"])
    root.option_add("*Text.highlightThickness", 0)
    root.option_add("*Text.borderWidth", 0)

    # Listbox : c'est le widget qui trahit le plus vite un theme sombre.
    root.option_add("*Listbox.background", T["bg_field"])
    root.option_add("*Listbox.foreground", T["ink"])
    root.option_add("*Listbox.selectBackground", T["acc_lo"])
    root.option_add("*Listbox.selectForeground", T["ink"])
    root.option_add("*Listbox.highlightThickness", 0)
    root.option_add("*Listbox.borderWidth", 0)
    root.option_add("*Listbox.relief", "flat")
    root.option_add("*Listbox.activeStyle", "none")

    # Scale classique (le ttk.Scale n'affiche pas sa valeur, on garde donc
    # parfois le tk.Scale) : fond, glissiere et curseur.
    root.option_add("*Scale.background", T["bg_panel"])
    root.option_add("*Scale.foreground", T["ink"])
    root.option_add("*Scale.troughColor", T["bg_field"])
    root.option_add("*Scale.activeBackground", T["acc"])
    root.option_add("*Scale.highlightThickness", 0)
    root.option_add("*Scale.borderWidth", 0)
    root.option_add("*Scale.sliderRelief", "flat")

    # Entry et Checkbutton classiques, au cas ou
    root.option_add("*Entry.background", T["bg_field"])
    root.option_add("*Entry.foreground", T["ink"])
    root.option_add("*Entry.insertBackground", T["acc"])
    root.option_add("*Entry.highlightThickness", 0)
    root.option_add("*Checkbutton.background", T["bg_top"])
    root.option_add("*Checkbutton.foreground", T["ink"])
    root.option_add("*Checkbutton.selectColor", T["bg_field"])
    root.option_add("*Checkbutton.activeBackground", T["bg_top"])
    root.option_add("*Checkbutton.highlightThickness", 0)

    root.option_add("*Menu.background", T["bg_panel"])
    root.option_add("*Menu.foreground", T["ink"])
    root.option_add("*Menu.activeBackground", T["acc_lo"])
    root.option_add("*Menu.activeForeground", T["ink"])
    root.option_add("*Menu.borderWidth", 0)
    root.option_add("*Menu.relief", "flat")

    # Fond des fenetres secondaires (Toplevel)
    root.option_add("*Toplevel.background", T["bg_top"])

    # ---------------------------------------------------------------- socle
    st.configure(".",
                 background=T["bg_top"], foreground=T["ink"],
                 fieldbackground=T["bg_field"], bordercolor=T["line"],
                 lightcolor=T["bg_top"], darkcolor=T["bg_top"],
                 troughcolor=T["bg_field"], focuscolor=T["acc"],
                 font=FONT["body"], borderwidth=0, relief="flat")

    # --------------------------------------------------------------- frames
    for name, bg in (("TFrame", T["bg_top"]),
                     ("Panel.TFrame", T["bg_panel"]),
                     ("Deep.TFrame", T["bg_deep"]),
                     ("Rail.TFrame", T["bg_rail"]),
                     ("Card.TFrame", T["bg_panel_hi"])):
        st.configure(name, background=bg, borderwidth=0, relief="flat")

    # --------------------------------------------------------------- labels
    st.configure("TLabel", background=T["bg_top"], foreground=T["ink"],
                 font=FONT["body"])
    st.configure("H1.TLabel", font=FONT["h1"], foreground=T["ink"],
                 background=T["bg_panel"])
    st.configure("H2.TLabel", font=FONT["h2"], foreground=T["ink"])
    st.configure("Dim.TLabel", foreground=T["ink_dim"], font=FONT["small"])
    st.configure("Sil.TLabel", foreground=T["ink_label"], font=FONT["label"])
    st.configure("SilPanel.TLabel", foreground=T["ink_label"],
                 font=FONT["label"], background=T["bg_panel"])
    st.configure("Data.TLabel", foreground=T["ink"], font=FONT["data"])
    st.configure("Ok.TLabel", foreground=T["ok"], font=FONT["small"])
    st.configure("Warn.TLabel", foreground=T["warn"], font=FONT["small"])
    st.configure("Err.TLabel", foreground=T["err"], font=FONT["small"])
    st.configure("PanelDim.TLabel", foreground=T["ink_dim"],
                 font=FONT["small"], background=T["bg_panel"])

    # -------------------------------------------------------------- boutons
    #  Secondaire : contour discret, se remplit au survol.
    st.configure("TButton",
                 background=T["bg_panel"], foreground=T["ink"],
                 bordercolor=T["line_strong"], lightcolor=T["bg_panel"],
                 darkcolor=T["bg_panel"], borderwidth=1, relief="flat",
                 focusthickness=0, padding=(14, 7), font=FONT["body"],
                 anchor="center")
    st.map("TButton",
           background=[("pressed", T["bg_deep"]), ("active", T["bg_panel_hi"]),
                       ("disabled", T["bg_panel"])],
           foreground=[("disabled", T["ink_ghost"])],
           bordercolor=[("active", T["acc"]), ("focus", T["acc"])],
           lightcolor=[("active", T["bg_panel_hi"])],
           darkcolor=[("active", T["bg_panel_hi"])])

    #  Primaire : plein cyan. Un seul par ecran.
    st.configure("Accent.TButton",
                 background=T["acc"], foreground=T["acc_ink"],
                 bordercolor=T["acc"], lightcolor=T["acc"],
                 darkcolor=T["acc"], borderwidth=1, relief="flat",
                 padding=(20, 8), font=FONT["h3"])
    st.map("Accent.TButton",
           background=[("pressed", T["acc_lo"]), ("active", T["acc_hi"]),
                       ("disabled", T["line"])],
           foreground=[("disabled", T["ink_ghost"])],
           lightcolor=[("active", T["acc_hi"]), ("pressed", T["acc_lo"])],
           darkcolor=[("active", T["acc_hi"]), ("pressed", T["acc_lo"])],
           bordercolor=[("active", T["acc_hi"])])

    #  Fantome : icone seule dans les barres.
    st.configure("Ghost.TButton",
                 background=T["bg_panel"], foreground=T["ink_dim"],
                 borderwidth=0, padding=(8, 5), font=FONT["body"])
    st.map("Ghost.TButton",
           background=[("active", T["bg_panel_hi"])],
           foreground=[("active", T["ink"])])

    # ------------------------------------------------- entrees et listes
    #  Le bouton fleche de la Combobox tire son fond de "background" (pas de
    #  "fieldbackground") et clam le repeint selon l'etat. Sans cartographie
    #  explicite il retombe sur le gris clair du theme d'origine.
    for cls in ("TEntry", "TCombobox", "TSpinbox"):
        st.configure(cls,
                     fieldbackground=T["bg_field"], background=T["bg_panel"],
                     foreground=T["ink"], bordercolor=T["line"],
                     lightcolor=T["line"], darkcolor=T["line"],
                     arrowcolor=T["ink_label"], insertcolor=T["acc"],
                     selectbackground=T["acc_lo"], selectforeground=T["ink"],
                     borderwidth=1, relief="flat", padding=(8, 5))
        st.map(cls,
               background=[("readonly", T["bg_panel"]),
                           ("active", T["bg_panel_hi"]),
                           ("pressed", T["bg_deep"]),
                           ("disabled", T["bg_deep"])],
               bordercolor=[("focus", T["acc"]), ("hover", T["line_strong"])],
               lightcolor=[("focus", T["acc"])],
               darkcolor=[("focus", T["acc"])],
               arrowcolor=[("hover", T["acc"]), ("active", T["acc"]),
                           ("disabled", T["ink_ghost"])],
               foreground=[("disabled", T["ink_ghost"])],
               fieldbackground=[("readonly", T["bg_field"]),
                                ("disabled", T["bg_deep"])])

    # liste deroulante de la Combobox : widget Tk, pas ttk -> option database
    root.option_add("*TCombobox*Listbox.background", T["bg_panel"])
    root.option_add("*TCombobox*Listbox.foreground", T["ink"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["acc_lo"])
    root.option_add("*TCombobox*Listbox.selectForeground", T["ink"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.font", FONT["body"])

    # --------------------------------------------------- cases et radios
    #  Le theme clam ne lit PAS "indicatorcolor" (c'est le nom des themes
    #  default/alt). Il attend indicatorbackground pour le fond de la case et
    #  indicatorforeground pour la coche. Sans ca, l'etat coche est invisible.
    st.configure("TCheckbutton", background=T["bg_top"], foreground=T["ink"],
                 indicatorbackground=T["bg_field"],
                 indicatorforeground=T["acc_ink"],
                 indicatormargin=(1, 1, 6, 1),
                 bordercolor=T["line_strong"],
                 upperbordercolor=T["line_strong"],
                 lowerbordercolor=T["line_strong"],
                 focuscolor=T["acc"], padding=(2, 4), font=FONT["body"])
    st.map("TCheckbutton",
           indicatorbackground=[("selected", T["acc"]),
                                ("active", T["bg_panel_hi"]),
                                ("disabled", T["bg_deep"])],
           indicatorforeground=[("selected", T["acc_ink"]),
                                ("disabled", T["ink_ghost"])],
           upperbordercolor=[("selected", T["acc"]), ("active", T["acc"])],
           lowerbordercolor=[("selected", T["acc"]), ("active", T["acc"])],
           foreground=[("disabled", T["ink_ghost"])],
           background=[("active", T["bg_top"])])

    #  Radio : on garde la pastille sombre et c'est le point qui s'allume.
    st.configure("TRadiobutton", background=T["bg_top"], foreground=T["ink"],
                 indicatorbackground=T["bg_field"],
                 indicatorforeground=T["acc"],
                 indicatormargin=(1, 1, 6, 1),
                 bordercolor=T["line_strong"],
                 upperbordercolor=T["line_strong"],
                 lowerbordercolor=T["line_strong"],
                 focuscolor=T["acc"], padding=(2, 4), font=FONT["body"])
    st.map("TRadiobutton",
           indicatorforeground=[("selected", T["acc"]),
                                ("!selected", T["bg_field"]),
                                ("disabled", T["ink_ghost"])],
           upperbordercolor=[("selected", T["acc"]), ("active", T["acc"])],
           lowerbordercolor=[("selected", T["acc"]), ("active", T["acc"])],
           foreground=[("selected", T["ink"]), ("disabled", T["ink_ghost"])],
           background=[("active", T["bg_top"])])

    # --------------------------------------------------------- LabelFrame
    st.configure("TLabelframe", background=T["bg_top"],
                 bordercolor=T["line_soft"], borderwidth=1, relief="solid")
    st.configure("TLabelframe.Label", background=T["bg_top"],
                 foreground=T["ink_label"], font=FONT["label"])

    # -------------------------------------------------------- Progressbar
    st.configure("TProgressbar", background=T["acc"], troughcolor=T["bg_field"],
                 bordercolor=T["bg_field"], lightcolor=T["acc"],
                 darkcolor=T["acc"], borderwidth=0, thickness=4)
    st.configure("Thin.Horizontal.TProgressbar", thickness=3,
                 background=T["acc"], troughcolor=T["bg_deep"],
                 borderwidth=0, lightcolor=T["acc"], darkcolor=T["acc"])
    st.configure("Budget.Horizontal.TProgressbar", thickness=6,
                 background=T["ok"], troughcolor=T["bg_field"],
                 borderwidth=0, lightcolor=T["ok"], darkcolor=T["ok"])

    # ---------------------------------------------------------- Notebook
    #  Onglets plats, sans bord, souligne cyan sur l'onglet actif.
    st.configure("TNotebook", background=T["bg_top"], borderwidth=0,
                 tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab",
                 background=T["bg_top"], foreground=T["ink_label"],
                 bordercolor=T["bg_top"], lightcolor=T["bg_top"],
                 darkcolor=T["bg_top"], borderwidth=0,
                 padding=(16, 7), font=FONT["label"])
    st.map("TNotebook.Tab",
           background=[("selected", T["bg_field"]), ("active", T["bg_panel"])],
           foreground=[("selected", T["acc"]), ("active", T["ink"])],
           lightcolor=[("selected", T["bg_field"])],
           expand=[("selected", (0, 0, 0, 0))])

    # -------------------------------------------------------- Scrollbar
    st.configure("Vertical.TScrollbar",
                 background=T["line"], troughcolor=T["bg_deep"],
                 bordercolor=T["bg_deep"], arrowcolor=T["ink_label"],
                 lightcolor=T["line"], darkcolor=T["line"],
                 borderwidth=0, arrowsize=12, width=10)
    st.map("Vertical.TScrollbar",
           background=[("active", T["line_strong"]), ("pressed", T["acc_lo"])])
    st.configure("Horizontal.TScrollbar",
                 background=T["line"], troughcolor=T["bg_deep"],
                 bordercolor=T["bg_deep"], arrowcolor=T["ink_label"],
                 lightcolor=T["line"], darkcolor=T["line"],
                 borderwidth=0, arrowsize=12)
    st.map("Horizontal.TScrollbar",
           background=[("active", T["line_strong"]), ("pressed", T["acc_lo"])])

    # ------------------------------------------------------- Scale (slider)
    st.configure("TScale", background=T["bg_top"], troughcolor=T["bg_field"],
                 bordercolor=T["line"], lightcolor=T["acc"],
                 darkcolor=T["acc_lo"])
    st.map("TScale", background=[("active", T["bg_top"])])

    # --------------------------------------------------------- Treeview
    st.configure("Treeview",
                 background=T["bg_field"], fieldbackground=T["bg_field"],
                 foreground=T["ink"], bordercolor=T["line_soft"],
                 borderwidth=0, rowheight=26, font=FONT["body"])
    st.map("Treeview",
           background=[("selected", T["acc_lo"])],
           foreground=[("selected", T["ink"])])
    st.configure("Treeview.Heading",
                 background=T["bg_panel"], foreground=T["ink_label"],
                 bordercolor=T["line_soft"], borderwidth=0,
                 font=FONT["label"], padding=(8, 6), relief="flat")
    st.map("Treeview.Heading", background=[("active", T["bg_panel_hi"])])

    # -------------------------------------------------------- Separator
    st.configure("TSeparator", background=T["line_soft"])
    st.configure("Panedwindow", background=T["bg_deep"])
    st.configure("Sash", sashthickness=6, gripcount=0,
                 background=T["bg_deep"], bordercolor=T["bg_deep"])

    return FONT


# =============================================================================
#  5. GEOMETRIE : coin arrondi exact
# =============================================================================

def round_rect_points(x0, y0, x1, y1, r, steps=6):
    """Points d'un rectangle a coins arrondis, pour create_polygon.

    Contrairement a l'astuce classique smooth=True (qui produit une spline
    approximative et deforme les cotes courts), on echantillonne les quatre
    quarts de cercle : le rayon est exact, les cotes restent droits.
    """
    r = max(0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    if r <= 0:
        return [x0, y0, x1, y0, x1, y1, x0, y1]
    pts = []
    corners = ((x1 - r, y1 - r,   0.0),      # bas droite
               (x0 + r, y1 - r,  90.0),      # bas gauche
               (x0 + r, y0 + r, 180.0),      # haut gauche
               (x1 - r, y0 + r, 270.0))      # haut droite
    for cx, cy, a0 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + 90.0 * i / steps)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def corner_inset(dy, r):
    """Retrait horizontal a la hauteur dy dans la zone d'un coin de rayon r.

    Sert a decouper un degrade ligne par ligne sur une forme arrondie :
    a chaque y, on sait de combien rentrer a gauche et a droite.
    """
    if dy >= r:
        return 0.0
    return r - math.sqrt(max(0.0, r * r - (r - dy) * (r - dy)))


__all__ = ["TOK", "CAT", "SLOT_CAT", "SLOT_NAME", "SLOT_ORDER", "FONT",
           "UI_SCALE", "UI_LANG", "compute_scale", "scale_tokens",
           "set_ui_lang", "TX", "slot_name", "cat_label",
           "apply_theme", "mix", "lighten", "darken", "ramp", "luma", "sil",
           "round_rect_points", "corner_inset"]
