# GP180 Studio - port dari GP200 Studio (WIP)

- Rebranding GP200 -> GP180, pengaman protokol (SysEx diblokir), gp180_device.py,
  tools/extract_fw.py + data/gp180_fw/ (SnapTone pabrik, draf model). Lihat GP180_PORTING_NOTES.md.

- Valeton Suite V2.1.0 dibongkar: data/gp180_suite/, data/gp180_models_suite.json (348 entri resmi GP-180),
  tools/build_catalog_from_suite.py. Katalog aktif belum diganti (format .prst/protokol belum diketahui).
---

# Revision du 17/07/2026 — confrontation a `algorithm.xml`

## Ce qui a change et pourquoi

Jusqu'ici les tables venaient d'une **seule** source : l'extraction du firmware
V1.8.0. Une erreur d'extraction etait donc indetectable — rien ne permettait de
la contredire.

L'editeur officiel Valeton installe un fichier :

```
C:\Program Files\Valeton\GP-200\Resource\GP-200\File\algorithm.xml
```

Il contient les **noms officiels, les catalogues et les definitions completes de
parametres** des 305 algorithmes : c'est la source dont l'editeur lui-meme se
sert pour afficher ses menus. Deuxieme source, independante du firmware.

Verdict de la confrontation (`xml_diff.py`) :

```
SLOT_ACCEPTS  : 9 modules sur 11 exacts, 2 incomplets (SnapTone)
NOMS          : 275 communs, 270 identiques, 5 divergents
PARAMETRES    : 205 modeles — nombre=0  noms=6  slots=0  bornes=0 divergences
```

**L'extraction firmware etait juste.** Zero modele invente, zero slot faux, zero
borne fausse. La permutation Ping Pong `[Mix 0, Time 2, Feedback 1, Sync 3,
Trail 4]` est confirmee a l'identique par l'attribut `ID` officiel.

## Corrections appliquees

| Quoi | Detail | Gravite |
|---|---|---|
| `Harmony 1` / `Harmony 2` | -> `Harmonizer 1` / `Harmonizer 2` | **BLOQUANT** : `_norm()` n'absorbe pas l'ecart, `Tables.find()` levait `ValueError` |
| 6 noms de parametres | `Smooth`->`Smooth Mode` (x2), `Sense`->`Sens`, `A Sync`->`Sync A`, `B Sync`->`Sync B`, `Wow & Flutter`->`Wow &` | moyen |
| `Mess 2C+ 3`, `Dark LUX`, `Dark VIT` | -> `Mess2C+ 3`, `DARK LUX`, `DARK VIT` | cosmetique (`_norm()` absorbait deja) |
| **+10 SnapTone (cat 15)** | 5 en AMP, 5 en DST. `Gain/Volume/Bass/Middle/Treble`, slots 0-4 | la fonction NAM etait inaccessible |
| `SLOT_ACCEPTS` | `DST: [3,0,15]`, `AMP: [7,8,15]` | idem |
| sous-tables `models_*.json` | resynchronisees depuis `gp200_models_all.json` | coherence |

Total : **206 -> 216 modeles**. Apres patch, la re-verification donne
**285 communs, 283 noms identiques, 0 divergence de parametre**.

### Hypotheses du manuel — toutes confirmees

Les entrees marquees `man` dans `SLOT_ACCEPTS` (deduites du manuel, jamais
verifiees) sont **toutes exactes** d'apres les catalogues du XML : PRE accepte
bien cat 3 (ODs en pre) et cat 4 (Auto Swell/Hold/Freeze), DST accepte cat 0
(boosts), WAH cat 1 (Hammy), MOD cat 1. Les commentaires `obs`/`man` de
`gp200lib.py` peuvent passer a `xml`.

### SnapTone n'est PAS propose au modele

`compact_catalog()` n'itere que sur les categories 7, 8, 3, 0, 1, 5, 4, 11, 12,
6. La cat 15 en est absente, **volontairement** : un slot SnapTone est un slot de
capture *vide* tant que l'utilisateur n'y a rien charge. Le proposer produirait un
preset pointant vers du neant. Le decodage et la validation les comprennent ; la
generation ne les propose pas.

## Bug connu, NON corrige : les User IR

`flags` n'est pas un champ mysterieux : c'est **l'octet haut de l'id**. Le code
officiel est un uint32 `(cat << 24) | id`, que notre `<HBB` decoupe en
`(mid16, flags8, cat8)`. Un User IR a l'id `0x100000 + k`, donc `flags = 0x10`.
Les 128 presets d'usine ont tous `flags = 0`, coherent.

Consequences, toutes deux non corrigees a ce jour :

* `decode_prst` fait `tables.cab(mid) or tables.cab(mid, user=True)` et **ignore
  `flags`** : un User IR au slot 0 se decode en `SUP ZEP`, silencieusement.
* `encode_prst` ecrit `flags = 0` en dur et `Tables._cab_by_name` exclut les cabs
  user : **aucun User IR ne peut etre ecrit**.

Bloquant des qu'on veut utiliser des IR tierces (TONE3000). Ne bloque pas la
validation materielle.

## Deux hypotheses precedentes INFIRMEES

* **C-Chorus a bien un seul parametre.** Le XML confirme un unique `Mode`, de type
  `Combox` — un menu qui choisit le type de chorus. Les tables avaient raison.
* **`COMP4` float[4] = 0.1586 est du reliquat memoire.** Le XML donne 4 parametres,
  IDs 0-3. Le test T5 de `gp200_validate.py` produit ici un faux positif : ses
  avertissements « PLAUSIBLE, parametre manquant ? » sont a ignorer, le
  parametrage etant desormais confirme exact sur les 215 modeles.

## Ce qui reste a valider sur materiel

Une seule chose, et elle n'a pas bouge : **le GP-200 accepte-t-il un `.prst` que
nous avons fabrique ?** Le catalogue n'est plus une question ouverte.

Le plan de test destructif envisage (essais d'import pour sonder `SLOT_ACCEPTS`,
releve manuel de 255 lignes a l'ecran) est **caduc** : le XML l'a regle.

Ordre operatoire :

1. **Lire la version du firmware.** Valeton apparie strictement firmware et
   editeur (« Firmware V1.8.0 — Compatible Software v1.8.0 ») et la v1.8.0 ajoute
   des effets. `algorithm.xml` provient de l'editeur installe : si l'unite n'est
   pas en 1.8.0, ces tables ne la decrivent pas. Mettre a jour d'abord.
2. **Backup des 128 slots** via l'editeur, mis de cote.
3. `python gp200_validate.py dump\` sur les presets d'usine dumpes.
4. **Un** preset genere, importe dans le slot 128.

## Nouveaux outils

| Fichier | Role |
|---|---|
| `gp200_validate.py` | Confronte un dossier de `.prst` aux tables. 6 tests (structure, banc d'usine, ids connus, bornes, floats orphelins, round-trip) + couverture. `--carve` decoupe un backup monolithique, `--checklist` (desormais superflu) liste les releves ecran. |
| `xml_diff.py` | Rejoue la confrontation tables <-> `algorithm.xml`. **A relancer apres toute mise a jour du firmware.** |
| `patch_data.py` | Applique les correctifs de cette revision. Deja applique ; conserve pour tracabilite. |
| `xml_parsed.json` | `algorithm.xml` parse (305 entrees, catalogues inclus). |


---

# Revision du 17/07/2026 (2) — descriptions officielles

## `description_en.xml`

Deuxieme fichier de l'editeur : `Resource\GP-200\File\description_en.xml`.
Il porte la description que l'editeur affiche pour chaque algorithme, et **elle
nomme les marques** : « Based on Marshall(R) JCM800* », « Based on Peavey(R)
5150(R) (LEAD channel) », « Based on Mesa/Boogie(R) Mark II C+(TM) ».

Couverture : **305 / 305, aucun trou** — SnapTone compris.

## Le decodeur ecrit a la main est retire

`SYSTEM` contenait 12 lignes de correspondances marques ecrites a la main. Elles
couvraient ~40 modeles sur 305 et etaient justes a environ 90 % :

| Affirmation | Verdict officiel |
|---|---|
| `UK 800` = JCM800 | confirme |
| `UK 45` = JTM45 | confirme |
| `Green OD` = TS-808 | confirme |
| `EV 51` = Peavey 5150 | confirme |
| `Micro Boost` = MXR M133 | confirme |
| `Mess2C+` = Mark IIC+ | confirme |
| **`C-Chorus` = Boss CE-1** | **FAUX — c'est un Boss DC-2 Dimension C** |

Le DC-2 a 4 boutons pour 4 modes, des sorties stereo, un boitier violet ; le
`Mode` a 4 valeurs de nos tables, ce sont litteralement ses 4 boutons. Le CE-1
n'a rien de tout ca. Le prompt decrivait donc la mauvaise pedale au modele.

C'est l'argument de fond : le savoir humain injecte est bon a ~90 %, et les 10 %
restants sont invisibles. Les 305 descriptions officielles remplacent les 12
lignes.

## Ce qui a change

* `data/gp200_descriptions.json` (nouveau) — 305 modeles, champs `short`
  (1re phrase, ce qui part dans le prompt) et `full` (reserve).
* `make_descriptions.py` (nouveau) — le regenere depuis `description_en.xml`.
* `gp200lib.py` — `Tables.desc` + `Tables.description(id, cat, full=False)`.
  Chargement **optionnel** : sans le fichier, le catalogue reste utilisable.
* `gp200_agent.py` — `compact_catalog()` ajoute `-> description` sous chaque
  modele et apres chaque cab ; le bloc `DECODEUR DE NOMMAGE` de `SYSTEM` devient
  `MATERIEL MODELISE`, qui renvoie aux descriptions et interdit d'inventer une
  filiation quand Valeton n'en revendique pas.
* `xml_diff.py` — refuse desormais un XML sans `<Alg>`. Il acceptait
  `description_en.xml` en silence et **ecrasait `xml_parsed.json` avec du vide**.

Cout du prompt : **~9 100 -> ~11 808 tokens** (+29 %). Mis en cache, soit environ
**+0,007 $ par generation** — negligeable face aux 0,10-0,25 $ de la recherche
web. Le vrai gain est ailleurs : la recherche web n'a plus a compenser le fait
que le modele ignore ce qu'est un « Bad-KT ».

## `GP-200 Software Release Note.rtf` — le risque firmware, chiffre

```
V1.8.0 (15/12/2025)  latence systeme optimisee
                     DST : Tube | NR : Gate 3 | MOD : A-Chorus | DLY : Broken Delay
                     accordeur 425-455
V1.7.0 (21/03/2025)  import de fichiers NAM
V1.6.0 (20/09/2024)  PRE : OD 9, Yellow OD, Penesas, Super OD, Blues OD,
                     Harmonizer 1, Harmonizer 2 | MOD : Vibrato T
                     DLY : Ice Delay | RVB : Tube Spring
```

La 1.8.0 n'ajoute que **4 effets**, et les 4 sont deja dans nos tables (`Tube`
id=11 cat3, `Gate 3` id=33 cat0, `A-Chorus` id=0 cat4, `Broken Delay` id=50
cat11). Sur une unite en 1.7.0, le seul ecart porte donc sur ces 4 modeles.

**Correction du CHANGELOG precedent** : la mise a jour firmware n'est PAS un
prealable bloquant au dump, contrairement a ce qui y etait ecrit. On peut dumper
d'abord et mettre a jour ensuite. C'est la 1.7.0, pas la 1.8.0, qui a apporte
l'import NAM (donc SnapTone).

## Correctif — UnicodeDecodeError sous Windows (cp1252)

`build_exe.bat` echouait en `[6/6]` :

```
SELFTEST ECHEC : UnicodeDecodeError: 'charmap' codec can't decode
byte 0x9d in position 30385
  File "gp200lib.py", line 135, in __init__
    self.desc = json.load(open(os.path.join(datadir, "gp200_descriptions.json")))
  File "encodings\cp1252.py", line 23, in decode
```

**Cause.** Sous Windows, `open()` sans `encoding=` utilise la locale — cp1252 en
France — et non UTF-8. Le bug etait **latent depuis toujours** dans `gp200lib` :
tous les `json.load(open(...))` etaient vulnerables. Il ne s'est jamais declenche
parce que tous les fichiers `data/*.json` etaient de l'**ASCII pur**. Les
descriptions officielles y ont introduit les premiers caracteres non-ASCII (`(R)`,
`(TM)`), et le piege s'est referme. Sous Linux le defaut *est* UTF-8 : les tests
passaient.

**Correction, deux niveaux.**

1. `encoding="utf-8"` explicite sur **toutes** les E/S texte : `gp200lib.py` (4),
   `xml_diff.py` (3), `patch_data.py` (3), `gp200_validate.py` (1),
   `make_descriptions.py` (1). C'est le vrai correctif.
2. `make_descriptions.py` ecrit desormais avec `ensure_ascii=True` : le fichier
   redevient de l'**ASCII pur** (`\u00ae` au lieu du caractere brut). Il est ainsi
   lisible sous n'importe quelle locale, meme par un code qui oublierait
   `encoding=`. Ceinture et bretelles.

**Garde anti-regression.** Le selftest verifie maintenant que chaque `data/*.json`
se decode en ASCII, et echoue avec un message explicite sinon. Verifie : en
regenerant le fichier avec `ensure_ascii=False`, le selftest tombe bien.

Correction validee en simulant le defaut cp1252 de Windows, pas seulement sous
la locale UTF-8 de developpement.

---

# Revision du 18/07/2026 — confrontation au MATERIEL (128 presets exportes)

Premier export reel depuis l'unite : 128 fichiers .prst, tous 1224 octets (export
fichier par fichier, pas de blob a decouper).

## Resultats

**T1 STRUCTURE : 128/128 checksums valides.** La formule checksum, deduite d'UN
seul fichier (Petrucci), tient sur 128 fichiers qu'on n'a pas fabriques. L'inconnue
n1 est levee.

**T2 CATALOGUE : 1408/1408 slots concordants (100%).** Apparies PAR POSITION
(NN-L du nom de fichier), les 128 presets x 11 modules correspondent exactement a
l'extraction firmware, au (model_id, category) pres. Zero divergence.
> L'appariement par NOM donnait 4 faux ecarts : le banc a ete renomme entre
> l'extraction firmware et la version installee ('On The Way' -> 'Juan Fer
> Ramirez'). `match_factory` apparie desormais par position, repli sur le nom.

**T4 BORNES : 1 seul vrai cas** (Radio Cat, DLY Time=4). Les 114 autres etaient du
bruit : 76 modules DESACTIVES (floats arbitraires, benins) et 37 en mode SYNC ou
Time/Rate est un index de division rythmique hors de la plage ms. T4 ne teste plus
que les modules actifs, hors Time/Rate quand un Sync existe.

## Corrige dans l'appli (pas seulement le rapport)

**encode_prst clampait les valeurs Sync.** Un `Time=4` legitime (mode synchronise)
etait « corrige » vers 20 (borne ms). Desormais une valeur EXPLICITE (issue d'un
preset decode) n'est plus bornee ; seules les valeurs par defaut que nous
choisissons le sont. Sans ce fix, re-encoder un preset en mode Sync corrompait son
tempo.

## Deux lacunes de DECODAGE documentees (sans impact sur la generation)

1. **Parametres non extraits.** COMP (float[2,3]), COMP4 (float[4,5,6]), C-Chorus
   (float[1,2]), Gate 1 (float[1,2]), Mess... portent des valeurs coherentes et
   VARIABLES a des index que ni nos tables NI algorithm.xml n'exposent. 102 couples
   (modele, slot) varient selon les presets = vrais parametres sous-comptes ; 276
   sont constants (gabarit de bloc). Hypothese : parametres internes que l'editeur
   masque, ou slots partages entre modeles d'un meme gabarit.

2. **12e octet du bloc chain_order.** Cru padding, il porte une valeur variable
   (0/7/8/32/60/102/112 selon le preset). Champ non identifie.

**Pourquoi ca ne bloque pas la generation.** Le pipeline part d'une DESCRIPTION et
ecrit par-dessus `template.prst` : les floats non extraits et ce 12e octet sont
HERITES du template, jamais fabriques. C'est un enjeu de fidelite de round-trip
(re-encoder a l'identique un preset existant), pas de generation. Un preset genere
reste valide — T1 le confirme sur nos propres sorties.

## Round-trip a vide : ~95% bit a bit

Re-encoder un preset sans le modifier reproduit ~1165/1224 octets. Les ~59 restants
sont : ~51 octets de METADONNEES TEXTE (noms de parametres que l'editeur stocke dans
les records, que le decodeur ne conserve pas), le 12e octet chain_order, et le
checksum (recalcule). Aucun n'affecte le son.

## Nouveau : `--roundtrip`

```
python gp200_validate.py --roundtrip "dump\01-B 50s Plexi.prst"
```

Decode un preset, le re-encode SANS rien changer, rapporte les octets qui different
et ECRIT le fichier re-encode. **Test a faire AVANT tout import genere** : importer
d'abord ce fichier re-encode dans l'editeur. S'il est refuse, le probleme est dans
l'encodeur, pas dans la generation — ca isole le risque.

## Plan de test materiel

1. `--roundtrip` sur un preset d'usine -> importer le fichier re-encode dans un slot
   libre. **S'il charge et sonne comme l'original, la mecanique d'ecriture est bonne.**
2. Seulement ensuite : un preset genere depuis une description.

---

# Revision interface (18/07/2026) — nommage, cles chiffrees, copie, langues

## Nommage des dossiers (version B)

Format demande : **`Artiste - Titre - AAAAMMJJ - HHMMSS`**, espaces preserves.
Ex. `Metallica - Master of Puppets - 20260718 - 114610`.

* Le schema JSON demande au modele deux champs de plus, `artiste` et `titre`
  (le modele les connait deja puisqu'il fait la recherche du rig).
* Nouveau `safe_dirname()` : preserve les espaces, retire seulement les
  caracteres interdits par Windows/Mac (`\\ / : * ? " < > |`). `AC/DC` -> `AC DC`.
* Repli sur la demande brute si le modele ne remplit pas artiste/titre.
* Mode affinage : `<preset source> (affine) - AAAAMMJJ - HHMMSS`.

## Cles API dans l'interface, CHIFFREES

* Au **premier lancement** : dialogue langue, puis dialogue cles API. Fini
  l'edition manuelle de config.json.
* Modifiables ensuite via le bouton **Cles API...** des options.
* `gp200_secrets.py` : chiffrement **DPAPI** (portee utilisateur Windows). Les
  cles ne sont dechiffrables que par le compte Windows courant sur cette machine ;
  copier config.json ailleurs les rend illisibles. Prefixe `dpapi:` / `plain:`
  (repli hors Windows) ; une ancienne cle en clair reste lue puis re-chiffree au
  prochain enregistrement.
* `save_config()` chiffre a l'ecriture, `load_config()` dechiffre en memoire.

## Copie depuis le champ resultat

* Menu contextuel (clic droit) : **Copier / Tout copier / Tout selectionner**,
  + Ctrl+C et Ctrl+A. Sur le Resultat ET le Journal.
* Les zones ne sont plus `state="disabled"` (qui bloquait la selection souris)
  mais en **lecture seule via binding** : selectionnables et copiables, non
  editables.

## Langue FR / EN / ES

* `gp200_i18n.py` : toutes les chaines d'interface en 3 langues.
* Choisie au premier lancement, changeable **a la volee** dans les options
  (l'interface se reconstruit en conservant la demande en cours).
* La langue des **reponses du modele** suit la langue de la demande, pas celle
  de l'interface : ecris en francais -> reponse en francais, etc. Rien a forcer.

## Build

`build_exe.bat` embarque `gp200_i18n.py`, `gp200_secrets.py` (hidden-imports) et
attend 15 fichiers data (ajout de `gp200_descriptions.json`).

Interface testee sous serveur X virtuel : premier lancement, chiffrement/
dechiffrement des cles, copie presse-papier, bascule des 3 langues. Selftest OK.

---

# Revision 0.1 (18/07/2026) — traductions completes, version, don

## Traductions manquantes corrigees

La revision precedente avait laisse ~30 chaines en dur (surlignees sur la capture
utilisateur). Toutes branchees sur i18n desormais : radios Nouveau morceau /
Affiner, titres et sous-titres des deux modes, Charger un .prst, Recherche web,
Structure du morceau, Detection automatique, Forcer + roles (clean/crunch/
disto/lead), Generer / Affiner, Usage API, Remettre a zero, onglet Journal, tous
les libelles de cout (budget, depense, session, quota), les statuts (modeles,
genere, affine) et les hints de structure. Verifie dans les 3 langues sous X
virtuel : zero fuite francaise en EN/ES.

## Versionnage

* `APP_VERSION = "0.1"` dans gp200_i18n.py.
* Titre de la fenetre : "GP-200 Studio \u2014 ...  v0.1".
* Nom de l'exe : `dist\GP200_Studio_v0.1.exe`.

## Bouton "Faire un don" (PayPal)

* Bouton coeur en bas a droite, traduit (Faire un don / Donate / Donar).
* Ouvre le formulaire de don PayPal vers widmer.rudy@gmail.com (EUR).
* Note : pour un lien plus fiable, creer un PayPal.Me et remplacer DONATE_URL
  dans gp200_i18n.py.

## Build

`build_exe.bat` : exe nomme avec la version.

---

# Revision 0.1 (suite) — Perplexity, liens d'aide cles, PayPal.Me, don clignotant

## Perplexity comme 3e fournisseur

* API format OpenAI (`/chat/completions`, Bearer), **recherche web native** :
  pertinent pour identifier le vrai rig. Modeles sonar / sonar-pro /
  sonar-reasoning.
* `_call_perplexity()` + routage dans `call_api()`. Pas d'endpoint de liste de
  modeles cote Perplexity : liste statique. Pas de suivi de cout par appel.
* Cle `api_key_perplexity`, chiffree comme les autres (DPAPI).

## Aide a l'obtention des cles

Decision : pas d'IA sans cle (aucune option gratuite legale et durable). A la
place, le dialogue des cles affiche pour **chaque** fournisseur un lien
"Obtenir une cle ->" qui ouvre la page de creation :
* Claude   : console.anthropic.com/settings/keys
* Gemini   : aistudio.google.com/app/apikey
* Perplexity : perplexity.ai/settings/api

Dialogue des cles reconstruit pour 3 fournisseurs, cases masquees, bouton
Afficher.

## Don

* Lien **PayPal.Me** : https://paypal.me/mediatorsRIV (remplace le formulaire
  business).
* Bouton "\u2764 Faire un don" a **pulsation douce** : la couleur du texte
  oscille du rouge discret au rouge vif, ~1 cycle / 2 s. Attire l'oeil sans
  agresser. Aucune dependance : simple alternance de style ttk via after().

---

# Revision 0.1 (fin) — coquilles langue, langue de sortie, micro guitare

## Labels de fournisseurs traduits

Les 3 labels du menu Provider (Gemini / Claude / Perplexity) et les messages qui
les citaient restaient en francais quelle que soit la langue. Passes par i18n
(prov_gemini / prov_anthropic / prov_perplexity) via provider_label().

## Langue de sortie corrigee

Quand la demande etait neutre (juste "Titre - Artiste"), le modele redigeait en
francais meme en interface EN/ES. Nouvelle consigne lang_instruction() :
* suit la langue de la DEMANDE si elle est identifiable ;
* sinon (demande trop courte/neutre), rabat sur la langue de l'INTERFACE.
Appliquee en generation ET en affinage, y compris dans les retries. Les noms de
modeles/cabs/parametres ne sont jamais traduits.

## Selecteur de micro guitare

Nouveau menu "Micro guitare" : Non precise / Humbucker / Simple bobinage / P90 /
Actif (EMG). pickup_instruction() explique au modele l'effet du micro sur le
niveau et l'harmonique attaquant l'ampli, pour qu'il ajuste Gain/Presence/EQ :
humbucker = moins de gain, attention aux basses ; simple = plus clair, un peu plus
de presence ; actif = deja tres chaud/compresse, reduire le gain. Choix persiste
dans config.json.

---

# Revision 0.1 (correctifs langue ES) — exemples, libelles resultat, langue de sortie renforcee

Captures utilisateur en interface espagnole : deux fuites restantes.

## Exemples traduits

La liste deroulante "Exemples" etait codee en dur en francais ("son rythmique
album", "couplet clean et solo final"...). Passee par i18n (ex_1..8, exa_1..7) via
EXEMPLES_L() / EXEMPLES_AFFINE_L(), rafraichie au changement de langue.

## Libelles du resultat traduits

RIG IDENTIFIE / STRUCTURE / SECTION / axe / ecoute / fichier etaient en dur dans
_show(). Traduits (res_rig, res_structure, res_section, res_axe, res_ecoute,
res_file). Au passage, _show utilisait encore state="disabled" : corrige en
_readonly pour rester copiable.

## Langue de sortie du modele renforcee

Le contenu redige par le modele (recherche, structure, raisons...) sortait en
francais meme en interface ES, sur une demande neutre "Titre - Artiste". Cause : un
nom d'artiste anglophone (Metallica) poussait le modele hors de la langue voulue,
et la consigne (en queue, molle) etait ignoree.

Correction : lang_instruction() reecrite, IMPERATIVE, nomme la langue en toutes
lettres, avertit explicitement qu'un nom propre anglophone ne doit PAS changer la
langue, et placee EN TETE de la demande. Regle finale conciliant les deux besoins :
langue de l'interface par DEFAUT ; on ne suit la langue de la demande que si
l'utilisateur a ecrit en phrases completes dans une autre langue. Applique en
generation, affinage et retries.

---

# Revision 0.1 (correctif regression texte) — sortie vide, Rock n Hell, cout

## REGRESSION corrigee : plus de texte de sortie

Cause : la consigne de langue, rendue longue/imperative et placee EN TETE de la
demande, poussait le modele a ecrire du texte hors du JSON -> champs "recherche"/
"structure" vides a l'affichage. La generation des presets marchait, mais le
compte-rendu etait vide.

Correction : lang_instruction() redevient COURTE, entre parentheses, placee en
FIN de demande, et rappelle "reponds uniquement par l'objet JSON". Nomme toujours
la langue cible et l'avertissement sur les noms propres anglophones. Remise en fin
dans generate / refine / retry.

## Rock n Hell retire

L'exemple mentionnant "Rock n Hell" (groupe de l'auteur, non universel) devient
"...pour une intro" dans les 3 langues.

## Consommation API : uniquement le cout de la generation

L'affichage detaillait session cumulee + budget + quota minute. Simplifie : une
seule ligne "Cout de cette generation : $X" (Anthropic uniquement, seul provider
avec suivi de cout). generate() calcule le cout imputable a CE preset par
difference du cumul avant/apres, meme quand la boucle de correction fait plusieurs
appels. payload["_gen_cost"].

# Revision interface (23/07/2026) — refonte visuelle « Retro-Future Hardware »

Refonte complete de l'interface. **Le moteur n'a pas ete touche** : `gp200_agent.py`,
`gp200lib.py`, `gp200_setlist.py`, `gp200_secrets.py`, `gp200_i18n.py`,
`gp200_validate.py`, `template.prst` et `data/` sont identiques octet pour octet a
la revision precedente. Seule la couche de presentation change.

`SELFTEST OK : 216 modeles, 90 cabs, encodage 1224 o` — inchange.

## Deux fichiers nouveaux, zero dependance nouvelle

| Fichier | Role |
|---|---|
| `gp200_theme.py` | Jetons de design (couleurs, espacements, typo), utilitaires couleur, theme ttk complet, mise a l'echelle selon l'ecran, geometrie des coins arrondis |
| `gp200_ui.py` | Composants dessines au Canvas : `SignalRack`, `ModuleInspector`, `PresetList`, `GlowButton`, `VMeter`, `Well`, `Chip`, `Led`, `Silk`, `GradientStrip` |
| `design_preview.py` | Maquette autonome a donnees fictives (`python design_preview.py`), sans appel API |

`sv-ttk` **n'est plus utilise** : le theme est integre. L'application continue de
ne dependre que de la bibliotheque standard (Tkinter + urllib).

## La chaine de signal devient l'element central

Les 11 modules du preset s'affichent sur **une seule ligne**, dans l'ordre reel de
la chaine, relies par un cordon qui entre et sort par un jack sur le cote de
chaque carte. Couleur par famille : generateurs (`PRE`/`DST`/`AMP`) en bleu,
mise en forme (`NR`/`CAB`/`EQ`) en vert, effets (`WAH`/`MOD`/`DLY`/`RVB`/`VOL`)
en mauve. Un module bypasse est rendu en pointille — sur le GP-200 un slot n'est
jamais vide, il est desactive.

**La progression remplace la barre de progression.** Pendant une generation, le
cordon s'allume module par module et un point lumineux le parcourt. Il n'y a plus
d'indicateur indetermine qui tourne dans le vide.

## Inspecteur de module

Un clic sur une carte affiche **tous** les parametres du module dans un panneau
sous la chaine, avec une jauge sur les valeurs manifestement en 0-100. Les
valeurs hors echelle connue (temps de delay en ms, frequence de coupure en Hz)
n'ont volontairement pas de jauge.

Motivation : les cartes sont etroites et n'affichent qu'un parametre. Un `AMP`
Mess2C+ en expose six. Les cartes disent le **trajet**, l'inspecteur dit les
**valeurs**.

Lecture seule : ce panneau n'ecrit jamais dans un preset.

## Navigation dans les presets generes

Une generation ecrit 3 variantes par section, soit jusqu'a 9 fichiers. Jusqu'ici
seule la chaine du **dernier** preset ecrit etait affichee, sans indication de
quel preset il s'agissait.

La colonne de gauche liste desormais tous les presets produits. Un clic recompose
la chaine correspondante, l'inspecteur suit, et le chemin du fichier s'affiche
dans la barre d'etat. Les trois variantes d'une meme section partagent la couleur
de leur liseré. La liste se remplit apres une generation, apres un affinage, et au
chargement d'un `.prst`.

L'en-tete de la chaine porte le nom du preset affiche.

## Mise a l'echelle selon la resolution

Un facteur global est deduit de la resolution de l'ecran (borne a 0,85 - 1,30) et
applique aux cartes, aux espacements et aux polices. La fenetre s'ouvre a 90 % de
l'ecran, centree.

Le rack calcule ensuite sa propre echelle pour que les 11 modules tiennent sur une
ligne dans la largeur disponible. Verifie de 1366x768 a 2560x1440 : une ligne
partout. En dessous d'environ 600 px de large, repli sur plusieurs rangs avec
defilement, plafonne a deux rangs visibles.

## Mode sombre uniquement

Le bouton de bascule clair/sombre (☾/☀) est retire : le systeme Retro-Future n'a
qu'une palette. `_toggle_theme()` est conserve en methode inerte et la cle
`"theme"` de `config.json` est ignoree sans erreur — aucune migration necessaire.

## Corrections d'affichage

| Quoi | Detail |
|---|---|
| Couleurs en dur | Les 30 teintes codees en dur (`#060`, `#a00`, `#666`…) etaient pensees pour un fond clair et devenaient illisibles sur fond sombre. Toutes remappees sur les jetons du theme. |
| Cases a cocher | Le theme `clam` ignore `indicatorcolor` (nom des themes `default`/`alt`) : l'etat coche etait invisible. Passe a `indicatorbackground` / `indicatorforeground`. |
| Listes deroulantes | Le bouton fleche tirait son fond de `background` sans cartographie d'etat et restait gris clair. |
| « Chaine de signal » | Le libelle etait code en francais en dur : un utilisateur anglais ou espagnol le voyait en francais. |

## Libelles ajoutes

Les chaines propres au design (`Presets generes`, `Chaine de signal`,
`module %d sur %d`…) vivent dans un dictionnaire `_DTXT` **local a
`gp200_studio.py`**, avec une fonction `DT()` qui suit la langue courante.
`gp200_i18n.py` fait partie du moteur et n'est pas modifie.

## Build

`build_exe.bat` : `sv-ttk` retire du `pip install` ; `gp200_theme.py` et
`gp200_ui.py` ajoutes au controle de presence et aux `--hidden-import`.

## Pieges Tkinter rencontres, documentes dans le code

Trois erreurs qui ont coute une iteration chacune, notees en commentaire a
l'endroit concerne pour ne pas les refaire :

* **`self._w` est reserve.** `Misc._w` contient le chemin Tcl du widget (une
  chaine). L'utiliser pour stocker une largeur casse le widget ou se fait ecraser
  par lui. Les dimensions internes des composants sont donc `_cw` / `_ch`.
* **Ordre de `pack()`.** Un conteneur en `expand=True` declare avant un pied en
  `side="bottom"` absorbe toute la cavite et le pied se retrouve avec une hauteur
  nulle. Le pied doit etre packe en premier.
* **`ttk.Panedwindow` fige son separateur** d'apres la taille annoncee au premier
  calcul de geometrie. Un Canvas sans hauteur explicite annonce alors sa valeur
  par defaut (7 cm, ~265 px), et la reduction ulterieure ne ramene pas le
  separateur. Remplace par un empilage simple : le rack et l'inspecteur prennent
  la hauteur qu'ils demandent a chaque calcul, le bloc Resultat/Journal absorbe le
  reste.

## Limites connues de la couche graphique

* **Pas d'anticrenelage.** Tkinter n'en a pas : les arrondis et les halos
  presentent un leger escalier en diagonale, invisible a 100 % de zoom. C'est le
  plafond de la bibliotheque, seul un portage PyQt6 le franchirait.
* **L'inspecteur est en lecture seule.** Rendre les valeurs editables impliquerait
  de reecrire des `.prst` depuis l'interface, donc de toucher au moteur. Ce serait
  une decision a part entiere, pas un effet de bord du design.
