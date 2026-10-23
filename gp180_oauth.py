#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GP-180 Studio -- connexion par compte (OAuth PKCE), sans cle a coller.

L'utilisateur clique "Se connecter", son navigateur s'ouvre, il autorise
l'application, et l'appli recupere une cle API qui lui appartient.

Fonctionnement :

    1. On genere un secret aleatoire (code_verifier) et son empreinte SHA-256
       (code_challenge). Le secret ne quitte jamais la machine.
    2. On ouvre un mini serveur HTTP sur un port libre de localhost.
    3. On ouvre le navigateur sur l'URL d'autorisation du fournisseur.
    4. L'utilisateur se connecte et autorise, dans SON navigateur.
    5. Le fournisseur redirige vers localhost avec un code a usage unique.
    6. Le mini serveur attrape le code.
    7. On echange code + code_verifier contre une cle API.

JOURNAL DE DIAGNOSTIC
---------------------
L'exe est compile en --windowed : il n'a pas de console, donc toute exception
levee dans un thread disparait sans laisser la moindre trace. Chaque etape est
donc ecrite dans

    gp180_oauth.log       (a cote de l'exe ou du script)

Le fichier est ouvert et referme a chaque ligne : meme si l'application se
ferme brutalement, rien n'est perdu. La cle est masquee dans le journal, qui
peut donc etre transmis sans risque.

Dependances : bibliotheque standard uniquement.
"""

import base64
import datetime
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# =============================================================================
#  Journal
# =============================================================================

LOG_NAME = "gp180_oauth.log"
_log_cb = [None]          # callback optionnel vers le Journal de l'interface


def log_path():
    """A cote de l'exe si compile, sinon a cote du script."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, LOG_NAME)


def set_log_callback(fn):
    """Permet a l'interface d'afficher aussi les lignes dans son Journal."""
    _log_cb[0] = fn


def diag(msg):
    """Ecrit une ligne horodatee.

    Ne leve jamais : un journal ne doit pas casser ce qu'il observe.
    """
    line = "%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
                       msg)
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    cb = _log_cb[0]
    if cb:
        try:
            cb(line)
        except Exception:
            pass


def _mask(k):
    """Masque une cle pour le journal : debut et fin seulement."""
    if not k:
        return "(vide)"
    k = str(k)
    if len(k) > 16:
        return "%s...%s (%d car.)" % (k[:8], k[-4:], len(k))
    return "(%d car.)" % len(k)


# =============================================================================
#  Fournisseurs supportant la connexion par compte
# =============================================================================

OAUTH_PROVIDERS = {
    "openrouter": {
        "label":     "OpenRouter",
        "auth_url":  "https://openrouter.ai/auth",
        "token_url": "https://openrouter.ai/api/v1/auth/keys",
        "cb_path":   "/callback",
        "key_field": "key",
        "site":      "https://openrouter.ai",
    },
}

TIMEOUT_S = 300          # 5 minutes : creation de compte incluse


# =============================================================================
#  PKCE
# =============================================================================

def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def make_pkce():
    """Retourne (code_verifier, code_challenge) en methode S256."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


# =============================================================================
#  Mini serveur local
# =============================================================================

_PAGE = """<!doctype html><html lang="fr"><meta charset="utf-8">
<title>GP-180 Studio</title><link rel="icon" href="data:,">
<style>
 body{margin:0;height:100vh;display:flex;align-items:center;
      justify-content:center;background:#1a1a1a;color:#e0e8f0;
      font-family:'Segoe UI',system-ui,sans-serif}
 .c{text-align:center;max-width:26rem;padding:2.5rem;background:#212121;
    border:1px solid #333a3f;border-radius:12px}
 .m{width:44px;height:44px;margin:0 auto 1.2rem;border-radius:10px;
    background:linear-gradient(180deg,#3fc4e8,#12708d);color:#04222c;
    font-weight:700;font-size:17px;display:flex;align-items:center;
    justify-content:center}
 h1{font-size:1.05rem;margin:0 0 .5rem;letter-spacing:.06em;
    text-transform:uppercase;color:%(accent)s}
 p{margin:0;color:#8fa0b0;font-size:.9rem;line-height:1.5}
</style>
<div class="c"><div class="m">GP</div>
<h1>%(title)s</h1><p>%(msg)s</p></div>"""

_OK = {"accent": "#1a9fc7", "title": "Connexion reussie",
       "msg": "Tu peux fermer cet onglet et revenir a GP-180 Studio."}
_KO = {"accent": "#e2564a", "title": "Connexion annulee",
       "msg": "Aucune cle n'a ete recuperee. Retourne a GP-180 Studio "
              "pour reessayer."}


class _Catcher(BaseHTTPRequestHandler):
    """Attrape le retour du fournisseur.

    `timeout` est essentiel : sans lui, une connexion ouverte sans requete
    bloque la lecture indefiniment.

    Deux precautions :

    * Un navigateur ne fait pas UNE requete mais plusieurs (/favicon.ico,
      pre-chargement...). Seule la requete sur le chemin de callback compte,
      tout le reste recoit un 204 muet.
    * Une fois le code capture, on ne l'ecrase plus jamais.

    Chaque requete recue est journalisee : c'est ce qui permet de voir ce que
    le navigateur envoie reellement.
    """

    timeout = 8          # abandonne une connexion muette au bout de 8 s

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        diag("  <- requete GET %s   parametres: %s"
             % (u.path, ",".join(sorted(q)) or "aucun"))

        if u.path != self.server.cb_path:
            diag("     ignoree : ce n'est pas le chemin de callback (%s)"
                 % self.server.cb_path)
            self._empty()
            return

        if self.server.oauth_code:
            diag("     ignoree : code deja capture")
            self._empty()
            return

        code = (q.get("code") or [None])[0]
        err = (q.get("error") or [None])[0]
        self.server.oauth_code = code
        self.server.oauth_error = err
        diag("     CODE=%s   erreur=%s"
             % ("oui (%d car.)" % len(code) if code else "NON",
                err or "aucune"))

        body = (_PAGE % (_OK if code else _KO)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        try:
            self.wfile.flush()
        except Exception:
            pass
        self.server.done.set()

    def do_HEAD(self):
        diag("  <- requete HEAD %s (ignoree)" % self.path)
        self._empty()

    def _empty(self):
        try:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except Exception:
            pass

    def log_message(self, *a):
        pass


class _Server(ThreadingHTTPServer):
    """Serveur du callback, durci contre le comportement reel des navigateurs.

    Le piege : HTTPServer est MONO-THREAD. Or Chrome et Edge ouvrent des
    connexions TCP par anticipation ("preconnect") sans y envoyer la moindre
    requete. Le serveur en accepte une, se bloque en lecture dessus, et ne
    revient jamais verifier le drapeau d'arret -- si bien que shutdown()
    attend pour toujours. Le flux se figeait alors APRES avoir recupere la
    cle, sans jamais la transmettre a l'interface.

    Trois protections :
      * multi-thread : une connexion bloquee n'empeche plus d'en servir
        d'autres ni de s'arreter ;
      * threads demons : ils ne retiennent pas le processus a la fermeture ;
      * delai de lecture sur le handler (voir _Catcher.timeout) : une
        connexion muette finit par etre abandonnee.
    """
    daemon_threads = True
    allow_reuse_address = True


def _free_port():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


# =============================================================================
#  Le flux complet
# =============================================================================

def connect(provider="openrouter", timeout=TIMEOUT_S, log=None,
            open_browser=True, on_url=None):
    """Lance la connexion et retourne la cle API de l'utilisateur.

    Leve RuntimeError avec un message lisible en cas d'echec.
    Chaque etape est ecrite dans gp180_oauth.log.
    """
    def say(m):
        diag(m)
        if log:
            try:
                log(m)
            except Exception:
                pass

    diag("=" * 64)
    diag("DEBUT  provider=%s  timeout=%ds  exe_gele=%s  python=%s"
         % (provider, timeout, getattr(sys, "frozen", False),
            sys.version.split()[0]))
    diag("journal : %s" % log_path())

    p = OAUTH_PROVIDERS.get(provider)
    if not p:
        diag("ECHEC : fournisseur inconnu")
        raise RuntimeError("Fournisseur inconnu : %s" % provider)

    verifier, challenge = make_pkce()
    diag("PKCE  verifier=%d car.  challenge=%d car.  methode=S256"
         % (len(verifier), len(challenge)))

    try:
        port = _free_port()
    except Exception as e:
        diag("ECHEC : aucun port local disponible : %r" % e)
        raise RuntimeError("Impossible d'ouvrir un port local : %s" % e)
    callback = "http://localhost:%d%s" % (port, p["cb_path"])
    diag("port local=%d   callback=%s" % (port, callback))

    try:
        srv = _Server(("127.0.0.1", port), _Catcher)
    except Exception as e:
        diag("ECHEC : serveur local impossible a demarrer : %r" % e)
        raise RuntimeError(
            "Impossible de demarrer le service local sur le port %d.\n"
            "Un pare-feu ou un antivirus le bloque peut-etre.\n%s\n"
            "Journal : %s" % (port, e, log_path()))

    srv.oauth_code = None
    srv.oauth_error = None
    srv.cb_path = p["cb_path"]
    srv.done = threading.Event()

    th = threading.Thread(target=srv.serve_forever,
                          kwargs={"poll_interval": 0.2})
    th.daemon = True
    th.start()
    diag("serveur local demarre")

    url = p["auth_url"] + "?" + urllib.parse.urlencode({
        "callback_url": callback,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    diag("URL d'autorisation : %s" % url)

    try:
        if on_url:
            try:
                on_url(url)
            except Exception:
                pass

        opened = False
        if open_browser:
            try:
                opened = bool(webbrowser.open(url))
            except Exception as e:
                diag("webbrowser.open a leve : %r" % e)
                opened = False
        diag("ouverture du navigateur : %s" % ("OK" if opened else "ECHEC"))

        if opened:
            say("Navigateur ouvert. Autorise l'application puis reviens ici.")
        else:
            say("Impossible d'ouvrir le navigateur automatiquement.")
            say("Ouvre cette adresse a la main :")
            say(url)

        diag("attente du retour (%d s max)..." % timeout)
        got = srv.done.wait(timeout)
        diag("attente terminee : %s"
             % ("retour recu" if got else "DELAI DEPASSE"))

        if not got:
            raise RuntimeError(
                "Delai depasse (%d s). Le navigateur n'est jamais revenu vers\n"
                "l'application.\nJournal : %s" % (timeout, log_path()))

        if srv.oauth_error:
            diag("ECHEC : autorisation refusee (%s)" % srv.oauth_error)
            raise RuntimeError("Autorisation refusee : %s" % srv.oauth_error)
        if not srv.oauth_code:
            diag("ECHEC : retour recu mais sans code")
            raise RuntimeError(
                "Le fournisseur est revenu sans code d'autorisation.\n"
                "Journal : %s" % log_path())

        say("Autorisation obtenue, recuperation de la cle...")
        key = _exchange(p, srv.oauth_code, verifier)
        diag("SUCCES  cle=%s" % _mask(key))
        say("Connecte.")
        return key
    except Exception:
        diag("TRACE COMPLETE :\n" + traceback.format_exc())
        raise
    finally:
        # Ceinture et bretelles : meme avec un serveur multi-thread, on ne
        # laisse JAMAIS l'arret bloquer le retour de la cle. Il part dans un
        # thread demon et on n'attend que brievement.
        def _stop(server):
            try:
                server.shutdown()
                server.server_close()
                diag("serveur local arrete")
            except Exception as e:
                diag("arret du serveur : %r" % e)

        t_stop = threading.Thread(target=_stop, args=(srv,))
        t_stop.daemon = True
        t_stop.start()
        t_stop.join(3)
        if t_stop.is_alive():
            diag("arret du serveur encore en cours (non bloquant)")
        diag("FIN")


def _exchange(p, code, verifier):
    """Echange le code a usage unique contre une cle API."""
    body = json.dumps({
        "code": code,
        "code_verifier": verifier,
        "code_challenge_method": "S256",
    }).encode("utf-8")
    diag("echange -> POST %s   (corps %d octets)"
         % (p["token_url"], len(body)))
    req = urllib.request.Request(
        p["token_url"], data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.getcode()
            raw = r.read().decode("utf-8")
        diag("echange <- HTTP %s   (%d octets)" % (status, len(raw)))
        d = json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        diag("echange <- HTTP %d   corps=%s" % (e.code, detail[:200]))
        hints = {
            400: "methode de challenge incoherente entre les deux etapes",
            403: "code ou code_verifier invalide, ou session expiree",
            405: "requete mal formee (POST et HTTPS obligatoires)",
        }
        raise RuntimeError("Echec de l'echange (HTTP %d%s)%s\nJournal : %s" % (
            e.code,
            " : " + hints[e.code] if e.code in hints else "",
            "\n" + detail if detail else "", log_path()))
    except urllib.error.URLError as e:
        diag("echange : reseau indisponible %r" % e.reason)
        raise RuntimeError("Reseau indisponible : %s\nJournal : %s"
                           % (e.reason, log_path()))
    except Exception as e:
        diag("echange : reponse illisible %r" % e)
        raise RuntimeError("Reponse illisible du fournisseur : %s\n"
                           "Journal : %s" % (e, log_path()))

    if isinstance(d, dict):
        diag("champs de la reponse : %s" % ",".join(sorted(d)))
    else:
        diag("reponse inattendue (pas un objet JSON)")
    key = d.get(p["key_field"]) if isinstance(d, dict) else None
    if not key:
        diag("ECHEC : pas de champ '%s' dans la reponse" % p["key_field"])
        raise RuntimeError("Reponse sans cle : %s\nJournal : %s"
                           % (json.dumps(d)[:200], log_path()))
    return key


# =============================================================================
#  Essai manuel, hors interface
# =============================================================================

if __name__ == "__main__":
    print("Journal :", log_path())
    try:
        k = connect(log=print)
        print("Cle obtenue :", _mask(k))
    except RuntimeError as e:
        print("Echec :", e)
