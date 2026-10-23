#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GP-180 Studio -- Composants d'interface "Retro-Future Hardware".

Widgets dessines au Canvas, en Tkinter pur. Aucune dependance externe :
pas de PIL, pas de sv_ttk, pas de ttkbootstrap. Tout ce que Tkinter ne sait
pas faire (coins arrondis, degrades, halo) est calcule ici a la main.

Aucune logique metier : ces classes ne connaissent ni les .prst, ni les API.
Elles recoivent des dicts et emettent des callbacks.

Contenu
    GradientStrip   bandeau a degre vertical (en-tete, pied)
    Silk            label serigraphie (majuscules interlettrees)
    Led             temoin lumineux avec halo
    Chip            pastille valeur/parametre
    GlowButton      bouton d'action primaire avec halo cyan
    VMeter          bargraph horizontal facon afficheur de rack
    SignalRack      LA piece maitresse : les 11 modules + la trace de signal
    PresetList      liste dense scrollable pour la barre laterale
"""

import math

# ATTENTION -- attributs reserves par Tkinter.
#   Misc._w est le CHEMIN TCL du widget (une chaine, ex. ".!frame.!canvas").
#   Ne jamais nommer un attribut self._w, self._name, self.master, self.tk ni
#   self.children dans une sous-classe de widget : on casse le widget ou on se
#   fait ecraser par lui. Les dimensions internes sont donc _cw / _ch.

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:                                    # pragma: no cover
    tk = ttk = None

from gp180_theme import (TOK, CAT, SLOT_CAT, FONT, UI_SCALE,
                         mix, lighten, darken, sil,
                         TX, slot_name, cat_label,
                         round_rect_points, corner_inset)


# =============================================================================
#  Primitives de dessin
# =============================================================================

def fill_round_rect(cv, x0, y0, x1, y1, r, top, bot, tags=(), step=2):
    """Rectangle arrondi rempli d'un degrade vertical, en Tkinter pur.

    Le Canvas Tk ne connait ni degrade ni transparence. On dessine le degrade
    ligne par ligne, et on rentre chaque ligne de la bonne quantite dans la
    zone des coins pour que l'arrondi soit net -- pas de crenelage en escalier
    comme avec un masque approximatif.
    """
    h = max(1.0, y1 - y0)
    y = y0
    while y < y1:
        t = (y - y0) / h
        c = mix(top, bot, t)
        ins = max(corner_inset(y - y0, r), corner_inset(y1 - y, r))
        cv.create_line(x0 + ins, y, x1 - ins, y, fill=c, width=step, tags=tags)
        y += step
    return cv.create_polygon(round_rect_points(x0, y0, x1, y1, r),
                             fill="", outline="", tags=tags)


def stroke_round_rect(cv, x0, y0, x1, y1, r, color, w=1, tags=(), dash=None):
    """Contour arrondi. dash=(3, 3) donne le liseré pointille des slots vides."""
    kw = dict(fill="", outline=color, width=w, tags=tags)
    if dash:
        kw["dash"] = dash
    return cv.create_polygon(round_rect_points(x0, y0, x1, y1, r), **kw)


def glow_round_rect(cv, x0, y0, x1, y1, r, color, bg, layers=4, spread=2.0,
                    tags=()):
    """Halo autour d'une forme arrondie.

    Sans canal alpha, on simule la diffusion en melangeant la couleur du halo
    vers la couleur de fond, couche par couche, en s'eloignant du bord.
    """
    for i in range(layers, 0, -1):
        t = i / float(layers + 1)
        c = mix(color, bg, 1.0 - (1.0 - t) * 0.9)
        d = spread * i
        stroke_round_rect(cv, x0 - d, y0 - d, x1 + d, y1 + d, r + d, c,
                          w=max(1, int(spread)), tags=tags)


def bevel(cv, x0, y0, x1, r, color, tags=()):
    """Liseré haut : la lumiere qui accroche l'arete superieure d'un chassis.

    Un seul filet de 1 px, mais c'est lui qui fait passer une carte plate
    pour une piece de materiel.
    """
    cv.create_line(x0 + r * 0.7, y0 + 0.5, x1 - r * 0.7, y0 + 0.5,
                   fill=color, width=1, tags=tags)


# =============================================================================
#  GradientStrip -- bandeau a degrade
# =============================================================================

class GradientStrip(tk.Canvas):
    """Bandeau plein largeur rempli d'un degrade vertical.

    Sert de fond a l'en-tete et au pied. Les widgets ttk se posent par-dessus
    avec place() ou create_window().
    """

    def __init__(self, master, top=None, bot=None, height=64, line=None, **kw):
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        tk.Canvas.__init__(self, master, height=height,
                           bg=top or TOK["bg_top"], **kw)
        self._top = top or TOK["bg_top"]
        self._bot = bot or TOK["bg_bot"]
        self._line = line
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _=None):
        self.delete("bgfill")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        for y in range(0, h, 2):
            self.create_line(0, y, w, y,
                             fill=mix(self._top, self._bot, y / float(h)),
                             tags="bgfill")
        if self._line:
            self.create_line(0, h - 1, w, h - 1, fill=self._line, tags="bgfill")
        self.tag_lower("bgfill")


# =============================================================================
#  Silk -- label serigraphie
# =============================================================================

class Silk(tk.Label):
    """Petit label majuscule interlettre, couleur serigraphie.

    Tkinter n'a pas de letter-spacing : l'interlettrage est insere dans la
    chaine par gp180_theme.sil(). Reserve aux libelles courts.
    """

    def __init__(self, master, text="", bg=None, fg=None, sp=1, **kw):
        tk.Label.__init__(self, master, text=sil(text, sp),
                          bg=bg or TOK["bg_panel"], fg=fg or TOK["ink_label"],
                          font=FONT["label"], bd=0, highlightthickness=0, **kw)
        self._sp = sp

    def set(self, text):
        self.configure(text=sil(text, self._sp))


# =============================================================================
#  Led -- temoin lumineux
# =============================================================================

class Led(tk.Canvas):
    """Temoin rond avec halo. on=True -> cyan allume, sinon rouge sombre."""

    def __init__(self, master, on=True, size=10, color=None, bg=None, **kw):
        self._d = size
        self._bg = bg or TOK["bg_panel"]
        self._color = color or TOK["acc"]
        box = size + 8
        tk.Canvas.__init__(self, master, width=box, height=box, bg=self._bg,
                           highlightthickness=0, bd=0, **kw)
        self._on = on
        self._draw()

    def _draw(self):
        self.delete("all")
        c = (self._d + 8) / 2.0
        r = self._d / 2.0
        col = self._color if self._on else TOK["led_off"]
        if self._on:
            for i in (3, 2, 1):
                self.create_oval(c - r - i, c - r - i, c + r + i, c + r + i,
                                 fill=mix(col, self._bg, 1 - 0.22 * (4 - i)),
                                 outline="")
        self.create_oval(c - r, c - r, c + r, c + r, fill=col,
                         outline=mix(col, "#000000", 0.45))
        if self._on:
            self.create_oval(c - r * 0.45, c - r * 0.7, c + r * 0.1, c - r * 0.15,
                             fill=lighten(col, 0.55), outline="")

    def set(self, on):
        if on != self._on:
            self._on = on
            self._draw()


# =============================================================================
#  Chip -- pastille de valeur
# =============================================================================

class Chip(tk.Canvas):
    """Pastille 'LABEL  valeur'. Le label en serigraphie, la valeur en chasse
    fixe pour que les chiffres ne dansent pas quand ils changent."""

    def __init__(self, master, label="", value="", bg=None, fg=None,
                 accent=None, width=104, height=26, **kw):
        self._bg = bg or TOK["bg_panel"]
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._fg = fg or TOK["ink_label"]
        self._acc = accent or TOK["ink"]
        self._cw, self._ch = width, height
        self.set(label, value)

    def set(self, label, value):
        self.delete("all")
        w, h = self._cw, self._ch
        fill_round_rect(self, 1, 1, w - 1, h - 1, TOK["r_ctl"],
                        lighten(self._bg, 0.06), self._bg)
        stroke_round_rect(self, 1, 1, w - 1, h - 1, TOK["r_ctl"],
                          TOK["line_soft"])
        self.create_text(9, h / 2, text=sil(label), anchor="w",
                         fill=self._fg, font=FONT["micro"])
        self.create_text(w - 9, h / 2, text=str(value), anchor="e",
                         fill=self._acc, font=FONT["data"])


# =============================================================================
#  GlowButton -- action primaire
# =============================================================================

class GlowButton(tk.Canvas):
    """Bouton plein cyan avec halo. Un seul par ecran : c'est l'action.

    Etats : repos / survol (halo plus large, fond plus clair) / enfonce /
    desactive / occupe (le halo respire pendant un appel API).
    """

    def __init__(self, master, text="Generer", command=None, bg=None,
                 width=190, height=42, color=None, icon=None, **kw):
        self._bg = bg or TOK["bg_panel"]
        self._c = color or TOK["acc"]
        self._cw, self._ch = width, height
        tk.Canvas.__init__(self, master, width=width + 16, height=height + 16,
                           bg=self._bg, highlightthickness=0, bd=0,
                           cursor="hand2", **kw)
        self._text = text
        self._icon = icon
        self._cmd = command
        self._hover = False
        self._down = False
        self._enabled = True
        self._busy = False
        self._phase = 0.0
        self._job = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    # -- rendu ---------------------------------------------------------------
    def _draw(self):
        self.delete("all")
        x0, y0 = 8, 8
        x1, y1 = 8 + self._cw, 8 + self._ch
        r = TOK["r_ctl"] + 2

        if not self._enabled:
            fill_round_rect(self, x0, y0, x1, y1, r,
                            TOK["bg_panel_hi"], TOK["bg_panel"])
            stroke_round_rect(self, x0, y0, x1, y1, r, TOK["line"])
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=self._text,
                             fill=TOK["ink_ghost"], font=FONT["h3"])
            return

        base = self._c
        if self._down:
            base = TOK["acc_lo"]
        elif self._hover:
            base = TOK["acc_hi"]

        # halo : plus large au survol, respirant quand occupe
        layers = 5 if self._hover else 3
        spread = 1.6
        if self._busy:
            layers = 5
            spread = 1.3 + 0.9 * (0.5 + 0.5 * math.sin(self._phase))
        glow_round_rect(self, x0, y0, x1, y1, r, base, self._bg,
                        layers=layers, spread=spread)

        fill_round_rect(self, x0, y0, x1, y1, r,
                        lighten(base, 0.18), darken(base, 0.12))
        stroke_round_rect(self, x0, y0, x1, y1, r, lighten(base, 0.35))
        bevel(self, x0, y0, x1, r, lighten(base, 0.55))

        label = self._text if not self._icon else "%s   %s" % (self._icon,
                                                               self._text)
        self.create_text((x0 + x1) / 2, (y0 + y1) / 2 + (1 if self._down else 0),
                         text=label, fill=TOK["acc_ink"], font=FONT["h3"])

    # -- evenements ----------------------------------------------------------
    def _on_enter(self, _):
        if self._enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _):
        self._hover = self._down = False
        self._draw()

    def _on_press(self, _):
        if self._enabled:
            self._down = True
            self._draw()

    def _on_release(self, _):
        if self._enabled and self._down:
            self._down = False
            self._draw()
            if self._cmd:
                self._cmd()

    # -- api -----------------------------------------------------------------
    def configure(self, cnf=None, **kw):
        """Compatibilite ttk.Button : accepte text= et state=.

        Le reste de gp180_studio.py appelle btn.configure(text=...) et
        btn.configure(state="disabled") sans savoir que c'est un Canvas.
        On intercepte ces deux options et on passe le reste au Canvas.
        """
        redraw = False
        if "text" in kw:
            self._text = kw.pop("text")
            redraw = True
        if "state" in kw:
            self._enabled = str(kw.pop("state")) != "disabled"
            self.configure_cursor()
            redraw = True
        if kw or cnf is not None:
            tk.Canvas.configure(self, cnf, **kw)
        if redraw:
            self._draw()

    config = configure

    def configure_cursor(self):
        try:
            tk.Canvas.configure(self, cursor="hand2" if self._enabled
                                else "arrow")
        except tk.TclError:
            pass

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return "normal" if self._enabled else "disabled"
        return tk.Canvas.cget(self, key)

    def set_text(self, text):
        self._text = text
        self._draw()

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.configure_cursor()
        self._draw()

    def set_busy(self, on):
        """Halo respirant pendant un appel reseau. Coupe l'interaction."""
        self._busy = bool(on)
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if on:
            self._pulse()
        else:
            self._draw()

    def _pulse(self):
        self._phase += 0.22
        self._draw()
        self._job = self.after(60, self._pulse)


# =============================================================================
#  VMeter -- bargraph
# =============================================================================

class VMeter(tk.Canvas):
    """Bargraph a segments, facon afficheur de rack.

    Utilise pour patch_vol : le niveau de sortie du preset, lisible d'un coup
    d'oeil, avec un repere sur la valeur de reference de la setlist.
    """

    def __init__(self, master, width=170, height=12, segs=24, bg=None,
                 target=None, **kw):
        self._bg = bg or TOK["bg_panel"]
        self._cw, self._ch, self._n = width, height, segs
        self._target = target
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg=self._bg, highlightthickness=0, bd=0, **kw)
        self._v = 0.0
        self._draw()

    def set(self, v, target=None):
        self._v = max(0.0, min(1.0, float(v)))
        if target is not None:
            self._target = target
        self._draw()

    def _draw(self):
        self.delete("all")
        n, w, h = self._n, self._cw, self._ch
        sw = w / float(n)
        lit = int(round(self._v * n))
        for i in range(n):
            x = i * sw
            t = i / float(n - 1)
            if i < lit:
                c = TOK["ok"] if t < 0.62 else (TOK["warn"] if t < 0.85
                                                else TOK["err"])
            else:
                c = mix(TOK["bg_field"], self._bg, 0.35)
            self.create_rectangle(x + 0.5, 1, x + sw - 1.5, h - 1,
                                  fill=c, outline="")
        if self._target is not None:
            x = max(1, min(w - 1, self._target * w))
            self.create_line(x, 0, x, h, fill=TOK["ink"], width=1)


# =============================================================================
#  SignalRack -- la piece maitresse
# =============================================================================

class SignalRack(tk.Canvas):
    """Les 11 modules du GP-180 poses sur leur chaine de signal.

    Parti pris : la chaine n'est pas une decoration, c'est la structure. Les
    cartes sont disposees en serpentin (gauche->droite, puis droite->gauche)
    et reliees par une trace continue qui entre et sort par un jack sur le
    cote de chaque carte. On lit le trajet du son comme sur un schema de
    pedalier.

    Et le detail qui fait tout : pendant une generation, ce n'est pas une
    barre de progression qui bouge, c'est la trace qui s'allume module par
    module. La progression EST le chemin du signal.

    Donnees attendues -- une liste de dicts :
        {"slot": "AMP", "model": "EV 51", "on": True,
         "params": {"Gain": 62, "Bass": 50, "Treble": 55}}
    Un slot absent de la liste est rendu en pointille avec un '+'.
    """

    def __init__(self, master, on_click=None, cols=None, bg=None, **kw):
        self._bg = bg or TOK["bg_rail"]
        tk.Canvas.__init__(self, master, bg=self._bg, highlightthickness=0,
                           bd=0, **kw)
        self._slots = []
        self._on_click = on_click
        self._cols_forced = cols
        self._hover = -1
        self._sel = -1
        self._progress = -1        # index du dernier module allume
        self._boxes = []           # (x0, y0, x1, y1) par carte
        self._flow_job = None
        self._flow_t = 0.0
        self._S = 1.0              # echelle courante, recalculee a chaque rendu
        self._last_h = -1          # derniere hauteur demandee (anti-boucle)
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(-1))
        self.bind("<Button-1>", self._on_click_evt)
        # En fenetre etroite la grille passe a 2 puis 1 colonne et depasse :
        # le Canvas defile de lui-meme, pas besoin d'un conteneur externe.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(seq, self._wheel)

    def _wheel(self, e):
        d = -3 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 3
        self.yview_scroll(d, "units")
        return "break"

    # -- donnees -------------------------------------------------------------
    def set_slots(self, slots):
        """slots : liste de dicts (voir docstring). L'ordre = ordre de chaine."""
        self._slots = list(slots or [])
        self._sel = -1
        self._render()

    def set_progress(self, k):
        """Allume la trace jusqu'au module k inclus. -1 = tout eteint."""
        self._progress = k
        self._render()

    def start_flow(self):
        """Fait courir un point lumineux le long de la trace, en boucle."""
        self.stop_flow()
        self._flow_t = 0.0
        self._flow_step()

    def stop_flow(self):
        if self._flow_job:
            self.after_cancel(self._flow_job)
            self._flow_job = None
        self.delete("flowdot")

    def _flow_step(self):
        self._flow_t = (self._flow_t + 0.012) % 1.0
        self._draw_flow_dot()
        self._flow_job = self.after(30, self._flow_step)

    # -- geometrie -----------------------------------------------------------
    #
    #  Le rack ne s'impose pas une taille : il PREND la mesure de la place
    #  qu'on lui donne et choisit l'echelle la plus grande a laquelle les 11
    #  modules tiennent entierement. Sur un grand ecran les cartes sont
    #  pleines ; sur une petite fenetre elles se resserrent au lieu d'etre
    #  coupees. En dernier recours seulement, ca defile.
    #
    _STEPS = (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58)

    #  Echelle minimale acceptable en mode une-ligne. En dessous, les cartes
    #  deviennent illisibles et on repasse sur plusieurs rangs.
    _MIN_ONE_ROW = 0.46

    def _fit(self):
        """Choisit (echelle, colonnes, largeur, hauteur, gouttiere).

        PRIORITE ABSOLUE : les 11 modules sur UNE ligne. Une chaine de signal
        qui serpente sur deux rangs n'est plus une chaine -- on perd la seule
        chose que ce composant sait dire mieux qu'une liste. On calcule donc
        d'abord la largeur de carte qui fait tenir tout le monde de bout en
        bout, et on ne retombe sur plusieurs rangs que si ca devient illisible.
        """
        w = max(self.winfo_width(), 320)
        h = max(self.winfo_height(), 120)
        n = max(1, len(self._slots))
        pad = TOK["pad_md"]

        # --- 1. tentative sur une seule ligne.
        #     Deux passes : d'abord une gouttiere confortable, ou l'on VOIT le
        #     cordon entre les modules ; si ca ne suffit pas, on la resserre
        #     avant de renoncer. Perdre un peu d'air entre les cartes est
        #     toujours preferable a casser la chaine en deux rangs.
        for gf in (0.60, 0.32):
            g = max(6, int(TOK["gap"] * gf))
            avail = w - 2 * pad - (n - 1) * g
            if avail <= 0:
                continue
            s = min((avail / float(n)) / float(TOK["card_wc"]), 1.30)
            if s >= self._MIN_ONE_ROW:
                return (s, n, TOK["card_wc"] * s, TOK["card_hc"] * s, g)

        # --- 2. repli : plusieurs rangs, cartes larges
        last = None
        for sc in self._STEPS:
            cw = TOK["card_w"] * sc
            ch = TOK["card_h"] * sc
            gg = TOK["gap"] * sc
            cols = self._cols_forced or int((w - 2 * pad + gg) // (cw + gg))
            cols = max(1, min(cols, n))
            rows = int(math.ceil(n / float(cols)))
            need = 2 * pad + rows * ch + (rows - 1) * (gg + 14 * sc)
            last = (sc, cols, cw, ch, gg)
            if need <= h:
                return last
        return last

    def _layout(self):
        """Positionne les cartes en serpentin. Renvoie (hauteur, colonnes)."""
        self._boxes = []
        s, cols, cw, ch, g = self._fit()
        self._S = s
        self._cwc, self._chc, self._gc = cw, ch, g
        pad = TOK["pad_md"]
        n = len(self._slots)
        if n == 0:
            return pad, cols
        w = max(self.winfo_width(), 320)
        used = cols * cw + (cols - 1) * g
        x_off = max(pad, (w - used) / 2.0)
        rstep = ch + g + 14 * s
        for i in range(n):
            r, c = divmod(i, cols)
            if r % 2:                      # serpentin : rang impair inverse
                c = cols - 1 - c
            x0 = x_off + c * (cw + g)
            y0 = pad + r * rstep
            self._boxes.append((x0, y0, x0 + cw, y0 + ch))
        rows = int(math.ceil(n / float(cols)))
        return pad + rows * ch + (rows - 1) * (g + 14 * s) + pad, cols

    def required_height(self):
        h, _ = self._layout()
        return int(h)

    def _fnt(self, role):
        """Police du role, mise a l'echelle du rack."""
        fam, size, style = FONT[role]
        return (fam, max(6, int(round(size * self._S))), style)

    # -- rendu ---------------------------------------------------------------
    def _render(self):
        self.delete("all")
        if not self._slots:
            self._S = 1.0
            self._empty_state()
            return
        h, cols = self._layout()
        w = max(self.winfo_width(), 320)
        self.configure(scrollregion=(0, 0, w, int(h)))
        # En mode une-ligne le rack n'a pas besoin de toute la cavite : il
        # demande exactement sa hauteur et rend le reste a l'inspecteur.
        # En repli multi-rangs on PLAFONNE a deux rangs : au-dela, le rack
        # defilerait plutot que de repousser le resultat hors de l'ecran.
        # Le garde-fou de 3 px evite la boucle Configure -> resize -> Configure.
        need = int(h)
        cap = int(2 * self._chc + self._gc + 14 * self._S
                  + 2 * TOK["pad_md"])
        if need > cap:
            need = cap
        if abs(need - self._last_h) > 3:
            self._last_h = need
            self.configure(height=need)
        self._draw_trace(cols)
        for i in range(len(self._slots)):
            self._draw_card(i)
        if self._flow_job:
            self._draw_flow_dot()

    def _empty_state(self):
        w = max(self.winfo_width(), 320)
        h = max(self.winfo_height(), 140)
        cx, cy = w / 2.0, h / 2.0
        stroke_round_rect(self, cx - 150, cy - 42, cx + 150, cy + 42,
                          TOK["r_card"], TOK["line"], dash=(4, 4))
        self.create_text(cx, cy - 10, text=sil(TX("chain_empty")),
                         fill=TOK["ink_label"], font=FONT["label"])
        self.create_text(cx, cy + 14,
                         text=TX("chain_hint"),
                         fill=TOK["ink_ghost"], font=FONT["small"])
        self.configure(scrollregion=(0, 0, w, h))

    # -- le cordon -----------------------------------------------------------
    def _jacks(self, i, cols):
        """Points d'entree et de sortie d'une carte, selon le sens du rang."""
        x0, y0, x1, y1 = self._boxes[i]
        my = (y0 + y1) / 2.0
        rtl = (i // cols) % 2 == 1          # rang parcouru de droite a gauche
        if rtl:
            return (x1, my), (x0, my)
        return (x0, my), (x1, my)

    def _segments(self, cols):
        """Cordons VISIBLES entre les cartes, de l'entree a la sortie.

        On ne trace plus la traversee interne des cartes : le signal disparait
        dans le module et ressort de l'autre cote, comme sur un vrai pedalier.
        Chaque segment porte l'index du module dont depend son allumage.
        """
        segs = []
        n = len(self._slots)
        for i in range(n - 1):
            _, ext = self._jacks(i, cols)
            nent, _ = self._jacks(i + 1, cols)
            if abs(nent[1] - ext[1]) <= 2:
                segs.append((ext, nent, i))
            else:
                # saut de rang : on sort, on longe le bord, on rentre
                dx = 16 * self._S if (i // cols) % 2 == 0 else -16 * self._S
                b1 = (ext[0] + dx, ext[1])
                b2 = (ext[0] + dx, nent[1])
                segs.append((ext, b1, i))
                segs.append((b1, b2, i))
                segs.append((b2, nent, i))
        return segs

    def _draw_trace(self, cols):
        if not self._boxes:
            return
        S = self._S
        for a, b, owner in self._segments(cols):
            if owner <= self._progress:
                self.create_line(a[0], a[1], b[0], b[1],
                                 fill=mix(TOK["acc"], self._bg, 0.55),
                                 width=max(3, int(6 * S)), capstyle="round",
                                 tags="trace")
                self.create_line(a[0], a[1], b[0], b[1], fill=TOK["acc_hi"],
                                 width=max(1, int(2 * S)), capstyle="round",
                                 tags="trace")
            else:
                self.create_line(a[0], a[1], b[0], b[1], fill=TOK["line"],
                                 width=max(1, int(2 * S)), capstyle="round",
                                 tags="trace")
        # embases IN et OUT de la chaine
        ent0, _ = self._jacks(0, cols)
        _, ext1 = self._jacks(len(self._slots) - 1, cols)
        r = max(3, 5 * S)
        for pt in (ent0, ext1):
            self.create_oval(pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r,
                             fill=TOK["bg_deep"], outline=TOK["line_strong"],
                             tags="trace")
            self.create_oval(pt[0] - r * .4, pt[1] - r * .4,
                             pt[0] + r * .4, pt[1] + r * .4,
                             fill=TOK["acc_lo"], outline="", tags="trace")

    def _draw_flow_dot(self):
        """Point lumineux qui parcourt les cordons : l'appli travaille."""
        self.delete("flowdot")
        if not self._boxes:
            return
        _, cols = self._layout()
        segs = self._segments(cols)
        if not segs:
            return
        lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b, _o in segs]
        total = sum(lens)
        if total <= 0:
            return
        d = self._flow_t * total
        for (a, b, _o), L in zip(segs, lens):
            if d <= L:
                u = 0.0 if L == 0 else d / L
                x = a[0] + (b[0] - a[0]) * u
                y = a[1] + (b[1] - a[1]) * u
                for rr, tt in ((7, 0.75), (4, 0.4), (2, 0.0)):
                    rr *= self._S
                    self.create_oval(x - rr, y - rr, x + rr, y + rr,
                                     fill=mix(TOK["acc_hi"], self._bg, tt),
                                     outline="", tags="flowdot")
                break
            d -= L

    # -- une carte -----------------------------------------------------------
    def _draw_card(self, i):
        """Rendu d'une carte.

        Le contenu s'adapte a la place REELLE plutot qu'a des positions
        figees : sur une carte compacte on garde le code du slot, la LED et
        le nom du modele ; le sous-titre et les parametres n'apparaissent que
        s'il reste de la hauteur. Le detail complet est dans l'inspecteur.
        """
        d = self._slots[i]
        x0, y0, x1, y1 = self._boxes[i]
        S = self._S
        cw, ch = x1 - x0, y1 - y0
        slot = d.get("slot", "?")
        cat = CAT[SLOT_CAT.get(slot, "FX")]
        on = bool(d.get("on", True))
        model = d.get("model") or ""
        hov = (i == self._hover)
        sel = (i == self._sel)
        tag = "card%d" % i
        r = min(TOK["r_card"] * S, cw / 4.0)
        px = max(6.0, cw * 0.085)
        inner = cw - 2 * px

        # de quoi on a la place, du plus important au moins important
        show_sub = ch >= 92
        n_par = 2 if cw >= 168 else (1 if ch >= 76 else 0)

        def nchar(pxpc):
            return max(3, int(inner / max(1.0, pxpc * S)))

        # --- module bypasse : on montre l'emplacement, pas un trou
        if not on:
            if hov:
                glow_round_rect(self, x0, y0, x1, y1, r, TOK["line_strong"],
                                self._bg, layers=2, spread=1.4, tags=tag)
            fill_round_rect(self, x0, y0, x1, y1, r,
                            lighten(self._bg, 0.03), self._bg, tags=tag)
            stroke_round_rect(self, x0, y0, x1, y1, r,
                              cat["light"] if sel else
                              (TOK["line_strong"] if hov else TOK["line"]),
                              w=2 if sel else 1, dash=(4, 4), tags=tag)
            self.create_text(x0 + px, y0 + ch * 0.17, text=sil(slot),
                             anchor="w", fill=TOK["ink_ghost"],
                             font=self._fnt("label"), tags=tag)
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2 + ch * 0.05,
                             text="+",
                             fill=cat["light"] if hov else TOK["ink_ghost"],
                             font=(FONT["family_display"],
                                   max(11, int(22 * S)), "bold"), tags=tag)
            self.create_text((x0 + x1) / 2, y1 - ch * 0.14,
                             text=sil(TX("bypass")),
                             fill=TOK["ink_ghost"], font=self._fnt("micro"),
                             tags=tag)
            return

        # --- module actif
        top = lighten(cat["tint"], 0.14 if hov else 0.04)
        bot = lighten(cat["dark"], 0.06) if hov \
            else mix(cat["tint"], cat["dark"], 0.85)
        if hov or sel:
            glow_round_rect(self, x0, y0, x1, y1, r, cat["glow"], self._bg,
                            layers=5 if sel else 4, spread=1.6, tags=tag)
        fill_round_rect(self, x0, y0, x1, y1, r, top, bot, tags=tag)
        stroke_round_rect(self, x0, y0, x1, y1, r,
                          cat["light"] if sel else
                          (lighten(cat["dark"], 0.28) if hov
                           else mix(cat["dark"], TOK["line"], 0.5)),
                          w=2 if sel else 1, tags=tag)
        bevel(self, x0, y0, x1, r, lighten(cat["light"], 0.15), tags=tag)

        # arete de famille sur le bord gauche
        self.create_rectangle(x0 + 2 * S, y0 + ch * 0.09,
                              x0 + max(3.0, 4 * S), y1 - ch * 0.09,
                              fill=cat["light"] if (hov or sel)
                              else mix(cat["light"], bot, 0.42),
                              outline="", tags=tag)

        # code du slot + LED d'ecriture
        ty = y0 + ch * 0.17
        self.create_text(x0 + px, ty, text=sil(slot), anchor="w",
                         fill=cat["light"], font=self._fnt("label"), tags=tag)
        lx = x1 - max(9.0, px * 0.9)
        lit = (self._progress < 0) or (i <= self._progress)
        lc = TOK["acc"] if lit else TOK["led_off"]
        lr = max(2.0, 3 * S)
        if lit:
            for k in (3, 2, 1):
                dd = k * S
                self.create_oval(lx - lr - dd, ty - lr - dd, lx + lr + dd,
                                 ty + lr + dd,
                                 fill=mix(lc, bot, 1 - 0.2 * (4 - k)),
                                 outline="", tags=tag)
        self.create_oval(lx - lr, ty - lr, lx + lr, ty + lr, fill=lc,
                         outline=darken(lc, 0.4), tags=tag)

        # nom du modele : la donnee la plus importante
        self.create_text(x0 + px, y0 + ch * 0.40,
                         text=_ellipsis(model, nchar(7.2)), anchor="w",
                         fill=TOK["ink"], font=self._fnt("h3"), tags=tag)
        if show_sub:
            self.create_text(x0 + px, y0 + ch * 0.56,
                             text=_ellipsis(slot_name(slot), nchar(6.0)),
                             anchor="w", fill=mix(cat["light"], bot, 0.45),
                             font=self._fnt("small"), tags=tag)

        # parametres : ce qui rentre, le reste est dans l'inspecteur
        params = list((d.get("params") or {}).items())
        if n_par and params:
            sy = y0 + ch * 0.66
            self.create_line(x0 + px, sy, x1 - px, sy,
                             fill=mix(cat["light"], bot, 0.78), tags=tag)
            shown = params[:n_par]
            cell = inner / float(len(shown))
            for k, (pk, pv) in enumerate(shown):
                cx = x0 + px + k * cell
                self.create_text(cx, y0 + ch * 0.79,
                                 text=sil(_ellipsis(pk,
                                                    max(3, int(cell /
                                                               (5.4 * S))))),
                                 anchor="w",
                                 fill=mix(cat["light"], bot, 0.35),
                                 font=self._fnt("micro"), tags=tag)
                self.create_text(cx, y0 + ch * 0.92, text=_num(pv), anchor="w",
                                 fill=TOK["ink"], font=self._fnt("data_b"),
                                 tags=tag)
            # combien de reglages en plus attendent dans l'inspecteur
            rest = len(params) - len(shown)
            if rest > 0:
                self.create_text(x1 - px, y0 + ch * 0.92, text="+%d" % rest,
                                 anchor="e", fill=mix(cat["light"], bot, 0.3),
                                 font=self._fnt("micro"), tags=tag)

        # embases de jack : la carte est branchee dans la chaine
        my = (y0 + y1) / 2.0
        jr = max(2.0, 3 * S)
        for jx in (x0, x1):
            self.create_oval(jx - jr, my - jr, jx + jr, my + jr,
                             fill=darken(cat["dark"], 0.35),
                             outline=mix(cat["light"], bot, 0.6), tags=tag)

    def select(self, i, notify=False):
        """Selectionne une carte depuis le code (sans clic de l'utilisateur)."""
        if not self._slots:
            return None
        i = max(0, min(int(i), len(self._slots) - 1))
        old, self._sel = self._sel, i
        for k in (old, i):
            if 0 <= k < len(self._slots):
                self.delete("card%d" % k)
                self._draw_card(k)
        if notify and self._on_click:
            self._on_click(i, self._slots[i])
        return self._slots[i]

    def selected(self):
        """(index, module) courant, ou (None, None)."""
        if 0 <= self._sel < len(self._slots):
            return self._sel, self._slots[self._sel]
        return None, None

    # -- interaction ---------------------------------------------------------
    def _hit(self, ex, ey):
        """Souris -> index de carte. Passe par canvasx/y : sans ca le survol
        se decale des que le rack defile."""
        x, y = self.canvasx(ex), self.canvasy(ey)
        for i, (x0, y0, x1, y1) in enumerate(self._boxes):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return -1

    def _set_hover(self, i):
        if i == self._hover:
            return
        old = self._hover
        self._hover = i
        for k in (old, i):
            if 0 <= k < len(self._slots):
                self.delete("card%d" % k)
                self._draw_card(k)
        self.configure(cursor="hand2" if i >= 0 else "")
        self.tag_raise("flowdot")

    def _on_motion(self, e):
        self._set_hover(self._hit(e.x, e.y))

    def _on_click_evt(self, e):
        i = self._hit(e.x, e.y)
        if i < 0:
            return
        old, self._sel = self._sel, i
        for k in (old, i):
            if 0 <= k < len(self._slots):
                self.delete("card%d" % k)
                self._draw_card(k)
        if self._on_click:
            self._on_click(i, self._slots[i])


def _ellipsis(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "\u2026"


def _num(v):
    """Affichage des valeurs de parametres : toujours en entier."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return "%d" % round(f)


# =============================================================================
#  PresetList -- barre laterale dense
# =============================================================================

class PresetList(tk.Frame):
    """Liste de presets, dense et scrollable.

    Chaque ligne : un liseré de couleur (famille dominante du preset), le nom,
    et une meta discrete. Dessinee au Canvas pour avoir la selection pleine
    largeur et le survol, que la Listbox Tk ne sait pas faire proprement.
    """

    ROW_H = 38

    def __init__(self, master, on_select=None, width=None, **kw):
        tk.Frame.__init__(self, master, bg=TOK["bg_panel"], bd=0,
                          highlightthickness=0, **kw)
        self._cw = width or TOK["sidebar_w"]
        self._on_select = on_select
        self._items = []
        self._sel = -1
        self._hover = -1

        self.cv = tk.Canvas(self, bg=TOK["bg_panel"], highlightthickness=0,
                            bd=0, width=self._cw)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview,
                                style="Vertical.TScrollbar")
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")

        self.cv.bind("<Configure>", lambda e: self._render())
        self.cv.bind("<Motion>", self._on_motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(-1))
        self.cv.bind("<Button-1>", self._on_click)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(seq, self._wheel)

    def set_items(self, items):
        """items : liste de dicts {'name', 'meta', 'cat'} ('cat' dans CAT)."""
        self._items = list(items or [])
        self._sel = -1
        self._render()

    def _wheel(self, e):
        d = -3 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 3
        self.cv.yview_scroll(d, "units")
        return "break"

    def _render(self):
        self.cv.delete("all")
        w = max(self.cv.winfo_width(), self._cw)
        h = self.ROW_H
        for i, it in enumerate(self._items):
            y = i * h
            cat = CAT.get(it.get("cat", "FX"), CAT["FX"])
            hov, sel = (i == self._hover), (i == self._sel)
            if sel:
                self.cv.create_rectangle(0, y, w, y + h,
                                         fill=mix(TOK["bg_panel"], cat["dark"],
                                                  0.55),
                                         outline="")
            elif hov:
                self.cv.create_rectangle(0, y, w, y + h,
                                         fill=TOK["bg_panel_hi"], outline="")
            # liseré de famille a gauche : on repere un preset a sa couleur
            self.cv.create_rectangle(0, y + 6, 3, y + h - 6,
                                     fill=cat["light"] if (sel or hov)
                                     else mix(cat["dark"], TOK["bg_panel"], 0.3),
                                     outline="")
            self.cv.create_text(14, y + 14, anchor="w",
                                text=_ellipsis(it.get("name", "?"), 24),
                                fill=TOK["ink"] if (sel or hov)
                                else TOK["ink_dim"], font=FONT["body"])
            self.cv.create_text(14, y + 28, anchor="w",
                                text=it.get("meta", ""),
                                fill=TOK["ink_label"] if sel
                                else TOK["ink_ghost"], font=FONT["micro"])
            self.cv.create_line(10, y + h, w - 10, y + h,
                                fill=TOK["line_soft"])
        self.cv.configure(scrollregion=(0, 0, w, max(len(self._items) * h, 1)))

    def _row_at(self, y):
        i = int(self.cv.canvasy(y) // self.ROW_H)
        return i if 0 <= i < len(self._items) else -1

    def _set_hover(self, i):
        if i != self._hover:
            self._hover = i
            self._render()

    def _on_motion(self, e):
        self._set_hover(self._row_at(e.y))

    def _on_click(self, e):
        i = self._row_at(e.y)
        if i < 0:
            return
        self._sel = i
        self._render()
        if self._on_select:
            self._on_select(i, self._items[i])


# =============================================================================
#  Well -- creux arrondi qui heberge un widget Tk
# =============================================================================

class Well(tk.Canvas):
    """Encadre un widget Tk carre (Text, Entry) dans un creux a coins arrondis.

    Tkinter ne sait pas arrondir un Text. On dessine donc le creux au Canvas
    et on y depose le widget avec create_window : le widget reste rectangulaire
    mais ses bords disparaissent dans le creux, et le contour arrondi est vrai.

    Usage :
        well = Well(parent, height=90)
        txt  = tk.Text(well, ...)
        well.mount(txt)
    """

    def __init__(self, master, bg=None, inner=None, pad=10, radius=None,
                 focus_color=None, **kw):
        self._bg = bg or TOK["bg_top"]
        self._inner = inner or TOK["bg_field"]
        self._pad = pad
        self._r = radius if radius is not None else TOK["r_ctl"]
        self._focus = focus_color or TOK["acc"]
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        tk.Canvas.__init__(self, master, bg=self._bg, **kw)
        self._child = None
        self._win = None
        self._focused = False
        self.bind("<Configure>", lambda e: self._render())

    def mount(self, child):
        self._child = child
        child.bind("<FocusIn>", lambda e: self._set_focus(True), add="+")
        child.bind("<FocusOut>", lambda e: self._set_focus(False), add="+")
        self._render()
        return child

    def _set_focus(self, on):
        self._focused = on
        self._render()

    def _render(self):
        self.delete("well")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        p = 2
        fill_round_rect(self, p, p, w - p, h - p, self._r,
                        darken(self._inner, 0.25), self._inner, tags="well")
        stroke_round_rect(self, p, p, w - p, h - p, self._r,
                          self._focus if self._focused else TOK["line"],
                          tags="well")
        self.tag_lower("well")
        if self._child is not None:
            pad = self._pad
            if self._win is None:
                self._win = self.create_window(
                    pad, pad, window=self._child, anchor="nw",
                    width=max(1, w - 2 * pad), height=max(1, h - 2 * pad))
            else:
                self.coords(self._win, pad, pad)
                self.itemconfigure(self._win, width=max(1, w - 2 * pad),
                                   height=max(1, h - 2 * pad))


# =============================================================================
#  ModuleInspector -- le detail complet d'un module
# =============================================================================

class ModuleInspector(tk.Canvas):
    """Tous les reglages du module selectionne dans le rack.

    Les cartes du rack sont volontairement etroites : elles disent le trajet
    du signal, pas le detail. Le detail est ici. On clique une carte, on voit
    l'integralite de ses parametres, avec une jauge sur ceux qui sont sur une
    echelle 0-100 pour comparer d'un coup d'oeil.

    Lecture seule : ce composant n'ecrit jamais dans un preset.
    """

    def __init__(self, master, bg=None, **kw):
        self._bg = bg or TOK["bg_rail"]
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        tk.Canvas.__init__(self, master, bg=self._bg, **kw)
        self._mod = None
        self._pos = None            # (index, total) pour situer dans la chaine
        self._last_h = -1           # derniere hauteur demandee (anti-boucle)
        self.bind("<Configure>", lambda e: self._render())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(seq, self._wheel)

    def _wheel(self, e):
        d = -3 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 3
        self.yview_scroll(d, "units")
        return "break"

    def set_module(self, mod, pos=None):
        """mod : dict {'slot','model','on','params'} ou None."""
        self._mod = mod
        self._pos = pos
        self._render()

    def _want(self, h):
        """Demande la hauteur exacte du contenu.

        Sans ca le panneau garde la part que lui donne le volet, quel que
        soit le nombre de reglages : un module a 3 parametres laissait un
        grand vide qui volait la place au texte du resultat.
        Garde-fou de 3 px : evite la boucle Configure -> resize -> Configure.
        """
        h = int(h)
        if abs(h - self._last_h) > 3:
            self._last_h = h
            self.configure(height=h)

    # -- rendu ---------------------------------------------------------------
    def _render(self):
        self.delete("all")
        w = max(self.winfo_width(), 240)
        h = max(self.winfo_height(), 80)
        if self._mod is None:
            self.create_text(w / 2, h / 2 - 8, text=sil(TX("no_module")),
                             fill=TOK["ink_label"], font=FONT["label"])
            self.create_text(w / 2, h / 2 + 14,
                             text=TX("no_module_hint"),
                             fill=TOK["ink_ghost"], font=FONT["small"])
            self.configure(scrollregion=(0, 0, w, h))
            self._want(int(64 * UI_SCALE[0]))
            return

        m = self._mod
        slot = m.get("slot", "?")
        cat = CAT[SLOT_CAT.get(slot, "FX")]
        on = bool(m.get("on", True))
        U = UI_SCALE[0]
        pad = TOK["pad_sm"]                 # marge verticale serree : chaque
        padx = TOK["pad_md"]                # pixel rendu ici va au resultat

        # ---- bandeau de tete. Le sous-titre et l'etat sont DANS le bandeau,
        #      cales a droite : ca economise une ligne entiere et il y a de
        #      la place a revendre sur cette largeur.
        hh = int(34 * U)
        fill_round_rect(self, padx, pad, w - padx, pad + hh, TOK["r_ctl"],
                        lighten(cat["tint"], 0.10),
                        mix(cat["tint"], cat["dark"], 0.8))
        stroke_round_rect(self, padx, pad, w - padx, pad + hh, TOK["r_ctl"],
                          mix(cat["dark"], TOK["line"], 0.4))
        self.create_rectangle(padx + 2, pad + 6, padx + 6, pad + hh - 6,
                              fill=cat["light"], outline="")
        cy = pad + hh / 2.0
        self.create_text(padx + 16, cy, text=sil(slot), anchor="w",
                         fill=cat["light"], font=FONT["label"])
        self.create_text(padx + 16 + int(54 * U), cy,
                         text=m.get("model") or "-", anchor="w",
                         fill=TOK["ink"], font=FONT["h2"])
        self.create_text(w - padx - 14, cy,
                         text=sil(TX("active")) if on else sil(TX("bypass")),
                         anchor="e", fill=TOK["acc"] if on else TOK["ink_ghost"],
                         font=FONT["micro"])
        sub = slot_name(slot)
        if self._pos:
            sub = "%s   -   %s" % (sub, TX("module_of", self._pos[0] + 1,
                                           self._pos[1]))
        self.create_text(w - padx - int(86 * U), cy, text=sub, anchor="e",
                         fill=mix(cat["light"], cat["dark"], 0.35),
                         font=FONT["small"])

        # ---- grille de parametres
        params = list((m.get("params") or {}).items())
        y0 = pad + hh + int(16 * U)
        if not params:
            self.create_text(pad + 2, y0 + 14,
                             text=TX("no_params"),
                             anchor="w", fill=TOK["ink_ghost"],
                             font=FONT["small"])
            self.configure(scrollregion=(0, 0, w, y0 + 40))
            self._want(y0 + int(34 * UI_SCALE[0]))
            return

        cell_w = int(166 * UI_SCALE[0])
        cols = max(1, int((w - 2 * pad) // cell_w))
        cell_w = (w - 2 * pad) / float(cols)
        cell_h = int(44 * UI_SCALE[0])

        for k, (pk, pv) in enumerate(params):
            r, c = divmod(k, cols)
            cx = pad + c * cell_w
            cy = y0 + r * cell_h
            self.create_text(cx, cy, text=sil(_ellipsis(str(pk), 18)),
                             anchor="nw", fill=TOK["ink_label"],
                             font=FONT["micro"])
            self.create_text(cx, cy + int(14 * UI_SCALE[0]), text=_num(pv),
                             anchor="nw", fill=TOK["ink"], font=FONT["data_b"])
            # jauge : uniquement sur les valeurs manifestement en 0-100.
            # Un temps de delay (440 ms) ou une frequence (8500 Hz) n'a pas
            # d'echelle connue ici : mieux vaut pas de jauge qu'une fausse.
            try:
                v = float(pv)
            except (TypeError, ValueError):
                continue
            if not (0.0 <= v <= 100.0):
                continue
            bx0 = cx
            bx1 = cx + cell_w - int(22 * UI_SCALE[0])
            by = cy + int(32 * UI_SCALE[0])
            if bx1 - bx0 < 20:
                continue
            self.create_line(bx0, by, bx1, by, fill=TOK["bg_field"],
                             width=max(3, int(4 * UI_SCALE[0])),
                             capstyle="round")
            self.create_line(bx0, by, bx0 + (bx1 - bx0) * (v / 100.0), by,
                             fill=cat["light"],
                             width=max(3, int(4 * UI_SCALE[0])),
                             capstyle="round")

        rows = int(math.ceil(len(params) / float(cols)))
        need = y0 + rows * cell_h + int(6 * UI_SCALE[0])
        self.configure(scrollregion=(0, 0, w, need))
        self._want(need)


__all__ = ["GradientStrip", "Silk", "Led", "Chip", "GlowButton", "VMeter",
           "SignalRack", "PresetList", "Well", "ModuleInspector",
           "fill_round_rect", "stroke_round_rect", "glow_round_rect", "bevel"]
