# -*- coding: utf-8 -*-
"""GP-180 Studio -- synchronise le numero de version avant compilation.

NE TOUCHE NI AU MOTEUR NI A L'INTERFACE. Ce script est un outil de build
externe, lance A LA MAIN avant `build_exe.bat`, separe du reste de l'appli.

Ce qu'il fait, dans l'ordre :
  1. Lit/cree version.json (local, A LA RACINE DU PROJET -- PAS distribue dans
     l'exe, sert uniquement d'aide-memoire et de source de verite pour toi).
  2. Ecrit la nouvelle version dedans.
  3. Remplace la ligne `APP_VERSION = "..."` dans gp180_i18n.py par la nouvelle
     valeur (simple remplacement de texte -- APP_VERSION reste une constante
     litterale comme avant, aucune lecture de fichier au runtime, aucun risque
     lie au packaging PyInstaller).
  4. Affiche le bloc pret a coller dans le version.json DE GITHUB (celui que
     l'appli va lire en ligne), pour eviter tout ecart de frappe entre les
     deux fichiers qui portent le meme nom mais des roles differents :
       - ./version.json          (local, source de verite pour TOI)
       - version.json sur GitHub (distant, lu par l'appli des UTILISATEURS)

Usage
-----
    python bump_version.py 0.2
    python bump_version.py 0.2 "Systeme de licence + notif de mise a jour"

Sans argument, affiche juste l'etat actuel (aucune modification).
"""
import json
import os
import re
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_VERSION_FILE = os.path.join(HERE, "version.json")
I18N_FILE = os.path.join(HERE, "gp180_i18n.py")
GITHUB_RELEASES_URL_DEFAULT = \
    "https://github.com/rudywidmer/GP200-Studio/releases/latest"

_VERSION_LINE_RE = re.compile(r'^APP_VERSION\s*=\s*"([^"]*)"', re.MULTILINE)


def _read_local():
    if not os.path.isfile(LOCAL_VERSION_FILE):
        return {"version": None, "notes": "", "updated": ""}
    try:
        with open(LOCAL_VERSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        sys.exit("Impossible de lire %s : %s" % (LOCAL_VERSION_FILE, e))


def _current_app_version():
    """Lit la version actuellement en dur dans gp180_i18n.py (verite terrain,
    au cas ou version.json local et le code auraient deja diverge)."""
    if not os.path.isfile(I18N_FILE):
        return None
    with open(I18N_FILE, "r", encoding="utf-8") as f:
        src = f.read()
    m = _VERSION_LINE_RE.search(src)
    return m.group(1) if m else None


def _write_local(version, notes):
    data = {
        "version": version,
        "notes": notes,
        "updated": datetime.date.today().isoformat(),
    }
    with open(LOCAL_VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return data


def _bump_i18n(version):
    with open(I18N_FILE, "r", encoding="utf-8") as f:
        src = f.read()
    matches = _VERSION_LINE_RE.findall(src)
    if len(matches) != 1:
        sys.exit("Attendu EXACTEMENT une ligne 'APP_VERSION = \"...\"' dans "
                 "%s, %d trouvee(s). Rien modifie, verifie le fichier a la "
                 "main." % (I18N_FILE, len(matches)))
    new_src, n = _VERSION_LINE_RE.subn(
        'APP_VERSION = "%s"' % version, src, count=1)
    if n != 1:
        sys.exit("Le remplacement a echoue. Rien modifie.")
    with open(I18N_FILE, "w", encoding="utf-8") as f:
        f.write(new_src)


def main(argv):
    current_code_version = _current_app_version()
    local = _read_local()

    if len(argv) < 2:
        print("Version actuelle dans gp180_i18n.py : %s" %
              (current_code_version or "(introuvable)"))
        print("Version dans version.json (local)    : %s" %
              (local.get("version") or "(aucun fichier)"))
        print()
        print("Usage : python bump_version.py <nouvelle_version> [\"notes\"]")
        return

    new_version = argv[1].strip()
    notes = argv[2].strip() if len(argv) > 2 else ""

    if not new_version:
        sys.exit("Version vide, abandon.")

    if current_code_version and current_code_version == new_version:
        print("gp180_i18n.py est deja en version %s -- rien a changer la."
              % new_version)
    else:
        _bump_i18n(new_version)
        print("gp180_i18n.py : APP_VERSION %r -> %r"
              % (current_code_version, new_version))

    data = _write_local(new_version, notes)
    print("version.json (local) mis a jour : %s" % LOCAL_VERSION_FILE)

    print()
    print("=" * 60)
    print("Prochaine etape MANUELLE : colle ce bloc dans version.json")
    print("SUR GITHUB (le fichier distant que lisent tes utilisateurs) :")
    print("=" * 60)
    gh_block = {
        "latest": new_version,
        "url": GITHUB_RELEASES_URL_DEFAULT,
        "notes": notes or ("Version %s." % new_version),
    }
    print(json.dumps(gh_block, ensure_ascii=False, indent=2))
    print("=" * 60)
    print("Rappel : ne colle ce bloc sur GitHub qu'UNE FOIS l'exe %s "
         "effectivement mis en ligne dans une Release -- sinon tes "
         "utilisateurs verront la notif avant de pouvoir telecharger quoi "
         "que ce soit." % new_version)


if __name__ == "__main__":
    main(sys.argv)
