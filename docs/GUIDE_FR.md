> **WIP GP-180**: format .prst, protokol USB, model dan preset masih data GP-200. Lihat GP180_PORTING_NOTES.md.

# GP-180 Studio — Guide d'utilisation (V0.91)

## C'est quoi ?

GP-180 Studio génère des presets (fichiers `.prst`) pour ton **Valeton GP-180**
à partir d'une simple description en texte. Tu écris ce que tu veux entendre,
une IA crée le preset, et tu n'as plus qu'à l'envoyer directement sur le GP-180
via USB.

Exemples de descriptions :
- *"Son clean cristallin avec chorus et reverb à ressort"*
- *"Crunch blues chaud style Stevie Ray Vaughan"*
- *"Metal moderne, gain saturé, gate serré, delay slapback"*
- *"Son lead Pink Floyd avec delay long et reverb ample"*


## Prérequis

- **Python 3.10+** installé (cocher *"Add python.exe to PATH"* à l'installation)
- **Tkinter** inclus (c'est le cas par défaut sur Windows si tu coches
  *"tcl/tk and IDLE"* à l'installation de Python)
- **Une clé API** pour au moins un des fournisseurs d'IA supportés (voir ci-dessous)
- **Pour le module Batch LUFS uniquement** : `pip install sounddevice pyloudnorm`
  (pas nécessaire pour la génération de presets)

La génération de presets n'utilise que la bibliothèque standard de Python.


## Installation

1. Extraire le contenu du zip dans un dossier de ton choix
2. Copier `config.example.json` en `config.json`
3. Ouvrir `config.json` avec un éditeur de texte et coller ta clé API
4. Double-cliquer sur `GP180_Studio.bat` (ou lancer `python gp180_studio.py`)

Au premier lancement, l'application te demandera de choisir le slot d'injection
GP-180 et de configurer tes clés API via une interface graphique.


## Obtenir une clé API

L'application a besoin d'une clé API pour communiquer avec un service d'IA.
**Cette clé est personnelle et les appels sont généralement à tes frais.**
Voici les options :

### Google Gemini — recommandé pour débuter
- **Coût** : gratuit (quota limité mais suffisant pour un usage normal)
- **Carte bancaire** : non requise
- **Lien** : https://aistudio.google.com/app/apikey
- **Procédure** : connecte-toi avec ton compte Google, clique sur
  *"Create API Key"*, copie la clé générée

### Anthropic Claude
- **Coût** : payant à l'usage (~0.003 à 0.015 $ par preset selon le modèle)
- **Carte bancaire** : requise (crédits prepaid, minimum ~5 $)
- **Lien** : https://console.anthropic.com/settings/keys

### OpenAI (ChatGPT)
- **Coût** : payant à l'usage (~0.002 à 0.01 $ par preset selon le modèle)
- **Carte bancaire** : requise (crédits prepaid)
- **Lien** : https://platform.openai.com/api-keys

### OpenRouter
- **Coût** : payant à l'usage, accès à des dizaines de modèles
- **Authentification** : via OAuth (pas de clé à saisir manuellement —
  un bouton *Se connecter* ouvre le navigateur et récupère la clé automatiquement)
- **Lien** : https://openrouter.ai

### Perplexity
- **Coût** : payant à l'usage (recherche web incluse dans le prix)
- **Carte bancaire** : requise
- **Lien** : https://www.perplexity.ai/settings/api

**Sécurité** : ta clé API est stockée localement dans ton `config.json`,
chiffrée sous Windows via DPAPI. Elle n'est jamais envoyée ailleurs qu'au
fournisseur d'IA que tu as choisi.


## L'interface

```
+------------------------------------------------------------------------+
| GP-180 STUDIO   Nouveau / Affiner   Langue  ⚙ Config  ★ Fonctionnalités|
+--------------------+---------------------------------------------------+
|  OPTIONS           |  DÉCRIS LE SON QUE TU VEUX                        |
|   fournisseur      |  [ zone de saisie ]                               |
|   modèle           |  EXEMPLES                                         |
|   micro guitare    |  STRUCTURE DU MORCEAU                             |
|   recherche web    |                                                   |
|                    |  CHAÎNE DE SIGNAL   <nom du preset affiché>       |
|  PRESETS GÉNÉRÉS   |  [PRE][WAH][DST][AMP][NR][CAB][EQ][MOD][DLY]...  |
|   > variante A     |  +-----------------------------------------+     |
|     variante B     |  | AMP  J-120 CL               module 4/11 |     |
|     variante C     |  | GAIN 25   BASS 40   MIDDLE 50   ...      |     |
|     ...            |  +-----------------------------------------+     |
|                    |                                                   |
|                    |  Résultat | Journal                               |
|                    |  [ compte-rendu détaillé ]                        |
+--------------------+---------------------------------------------------+
| ● statut   📍 01-A   🔌 Injecter        Setlist | ⚡ Générer les presets|
+------------------------------------------------------------------------+
```

L'interface s'adapte à la résolution de ton écran. La fenêtre s'ouvre à 90 %
de l'écran, centrée. Elle n'a qu'un mode sombre.

### La chaîne de signal

Les 11 modules du preset sont affichés **sur une seule ligne**, dans l'ordre réel
de la chaîne, reliés par un cordon comme sur un pédalier. La couleur indique le
rôle du module :

| Couleur | Modules | Rôle |
|---|---|---|
| **Bleu** | `PRE`, `DST`, `AMP` | ce qui fabrique le son |
| **Vert** | `NR`, `CAB`, `EQ` | ce qui le met en forme |
| **Mauve** | `WAH`, `MOD`, `DLY`, `RVB`, `VOL` | ce qui le colore |

Un module en pointillé est **bypassé** : sur le GP-180 un slot n'est jamais vide,
il est simplement désactivé.

Pendant une génération, **le cordon s'allume module par module** et un point
lumineux le parcourt — c'est l'indicateur de progression.

### L'inspecteur de module

**Clique sur un module** de la chaîne : tous ses réglages s'affichent juste en
dessous, avec une jauge pour les valeurs comprises entre 0 et 100.

Les cartes de la chaîne n'affichent qu'un paramètre (avec un `+5` qui indique
combien d'autres attendent). **Les cartes disent le trajet du signal,
l'inspecteur dit les valeurs.** Cet affichage est en lecture seule.

### L'éditeur live de slot

En cliquant sur un module **d'un preset chargé ou généré**, une fenêtre
**Live Control** s'ouvre si le GP-180 est connecté en USB. Tu peux y changer
le modèle d'effet et ajuster ses paramètres en temps réel, directement sur
le hardware, sans repousser tout le preset. Les modifications sont
répercutées dans le fichier `.prst` et visibles dans l'inspecteur.

### La LED GP-180

En bas à gauche, la pastille **● GP-180** indique l'état de la connexion USB :
- **Verte** : USB SysEx + Audio détectés (injection + LUFS disponibles)
- **Orange** : USB SysEx seul (injection OK, pas d'audio USB)
- **Grise** : GP-180 non détecté

### Naviguer dans les presets générés

Une génération écrit 3 variantes par section, jusqu'à 9 fichiers d'un coup.
La colonne de gauche les liste tous sous **PRESETS GÉNÉRÉS**.

Cliquer sur un preset recompose la chaîne et, si le GP-180 est connecté,
l'injecte automatiquement sur le slot configuré (📍). Le nom du preset affiché
apparaît à côté du titre *Chaîne de signal*.


## Utilisation

### Générer des presets (mode "Nouveau")

1. Choisis ton **fournisseur d'IA** et ton **modèle** dans les menus déroulants
2. Sélectionne le **type de micro** (humbucker, single coil, P90, actif) pour
   que l'IA adapte gain et EQ à ton guitare
3. Écris ta description dans la zone de texte (ou choisis un exemple)
4. Active ou désactive la **recherche web** (aide l'IA à identifier le vrai
   équipement d'un artiste, mais consomme plus de tokens)
5. Choisis la **structure** :
   - **Détection automatique** : l'IA décide combien de presets créer et
     comment les organiser (3, 6 ou 9 presets)
   - **Forcer les rôles** : tu coches les rôles que tu veux
     (`clean`, `crunch`, `disto`, `lead`) — 3 presets par rôle
6. Clique sur **Générer**
7. Les fichiers `.prst` sont écrits dans le dossier de sortie
   (par défaut `Documents\GP180_Presets`) et apparaissent dans la liste de
   gauche. Si le GP-180 est connecté, le premier preset est injecté
   automatiquement sur le slot configuré.

### Affiner un preset (mode "Affiner")

1. Passe en mode **Affiner** via le sélecteur en haut
2. Charge un fichier `.prst` existant : sa chaîne s'affiche immédiatement,
   avant tout appel à l'IA
3. Décris les modifications souhaitées en texte libre
   (*"plus de gain"*, *"enlève le delay"*, *"change l'ampli pour un Fender"*)
4. Clique sur **Affiner**
5. L'application montre les **changements réels** calculés sur le fichier
   (pas ce que le modèle prétend avoir fait), la chaîne mise à jour,
   et les éventuels avertissements (ex: ampli sans paramètre Volume)

Le preset d'origine n'est jamais modifié : une nouvelle version est écrite
dans un sous-dossier horodaté.

### Optimiser pour le concert

En mode Affiner, le bouton **Live Ready** adapte un preset fait à la maison pour
le jeu à fort volume : réduction du gain et des mix de reverb/delay,
coupe-haut sur le baffle contre la fizz, léger boost de médiums. L'intention
artistique et l'EQ créatif sont préservés. Aucune description à saisir —
le prompt est précâblé.

### Injecter un preset sur le GP-180 (USB)

Le bouton **🔌 Injecter** en bas à droite envoie le preset sélectionné
directement sur le GP-180 via USB SysEx.

- Le **slot cible** est affiché en permanence (📍 01-A par défaut) et
  configurable via un clic sur ce bouton
- Une **barre de progression** chunk par chunk confirme l'envoi (7 paquets)
- L'injection est aussi **automatique** à chaque sélection dans la liste,
  si l'option est activée dans le dialogue du slot
- Le **GP-180 doit être branché en USB** et reconnu (LED verte ou orange)

### Harmoniser les volumes (Batch LUFS)

Accessible via le menu **★ Fonctionnalités → 🎛 Batch Vol.**

Le module Batch LUFS mesure le volume réel de chaque preset (norme EBU R128)
et les calibre automatiquement à une cible commune, sans intervention manuelle.

**Principe** :
1. Charger les `.prst` dans l'ordre d'import sur le GP-180
2. Configurer l'entrée audio (interface USB du GP-180) et le slot de test
3. Cliquer **Lancer**
4. Pour chaque preset : jouer un accord en boucle — l'app mesure le LUFS
   et ajuste les paramètres via USB en temps réel
5. Validation automatique après 3 secondes de stabilité dans la tolérance (±0.4 dB)

**Cascade d'ajustement** (du plus transparent au moins transparent) :
- **Volume Ampli** (si le modèle en a un) — plage 25–100
- **Volume CAB** — plage 20–100
- **Patch Volume global** — plage 35–100
- **Gain Ampli** en dernier recours (+10 pts max sur la valeur initiale,
  uniquement si l'ampli n'a pas de volume séparé)

Deux types de presets : **NORMAL** (cible -16 dB LUFS) et **LEAD** (cible -11 dB
LUFS). Les fichiers corrigés sont sauvegardés dans un sous-dossier `out/`.

**Prérequis** : `pip install sounddevice pyloudnorm`

> ⚠️ **Driver USB Audio obligatoire pour le Batch LUFS** : pour que l'application
> puisse mesurer le signal audio du GP-180, le driver USB Audio Valeton doit être
> installé sur ton PC. Sans lui, l'interface *Ligne (Valeton GP-180)* n'apparaît
> pas dans la liste des entrées audio et la mesure LUFS est impossible.
>
> Le driver testé sur Windows 11 est disponible ici :
> https://www.valeton.net/wpfd_file/valeton-usb-asio-driver-v5-57-2-setup-zip/
>
> **Attention** : ce lien est fourni à titre indicatif. Il a fonctionné sur le
> setup de développement (Windows 11), mais il n'y a aucune garantie que ce
> driver fonctionne sur ton PC. En cas de problème, consulte le site Valeton
> (https://www.valeton.net) ou les forums utilisateurs GP-180.

### Changer de langue

Utilise le menu déroulant de langue en haut. Le changement est immédiat et
persiste entre les sessions. Langues disponibles : français, anglais, espagnol.

### Configurer les clés API et le dossier de sortie

Menu **⚙ Config** en haut à droite :
- **Clés API** : dialogue de saisie pour tous les fournisseurs
- **Dossier de sortie** : ouvre le dossier courant dans l'explorateur


## Envoyer les presets sur le GP-180

Utilise le bouton **🔌 Injecter** en bas à droite : le preset sélectionné est
envoyé directement sur le slot configuré (📍) via USB SysEx. C'est la seule
méthode de transfert supportée par GP-180 Studio.


## Suivi de consommation

Si tu utilises un fournisseur payant (Claude, OpenAI, Perplexity),
l'application affiche une estimation du coût de chaque génération.
Ce suivi est une estimation locale — vérifie ton solde réel sur le site du
fournisseur.

Tu peux définir un plafond dans `config.json` (`budget_usd`).

Gemini (Google) ne fournit pas de données de consommation côté client :
le suivi de coût n'est pas disponible pour ce fournisseur.


## Problèmes courants

| Symptôme | Solution |
|----------|----------|
| *"Clé API invalide"* | Vérifie la clé (pas d'espace en début/fin) et le fournisseur sélectionné |
| *"Modèle non reconnu"* | L'IA a halluciné un nom — reformule ta description |
| GP-180 non détecté (LED grise) | Vérifie le câble USB et que le driver Valeton est installé |
| Injection échouée | Débranche/rebranche le GP-180 et réessaie |
| Batch : pas de son mesuré | Vérifie que le driver USB Audio Valeton est installé et que l'entrée audio pointe sur *Ligne (Valeton GP-180)* |
| Batch : `sounddevice` introuvable | `pip install sounddevice pyloudnorm` |
| L'appli ne se lance pas | Vérifie Python dans le PATH (`python --version`) et Tkinter (`python -c "import tkinter"`) |
| Erreur réseau / timeout | Vérifie ta connexion internet et que le fournisseur d'IA est accessible |
| La chaîne s'affiche sur plusieurs rangs | La fenêtre est trop étroite — élargis-la ou passe en plein écran |
| L'interface paraît trop grande ou trop petite | Elle se cale sur la résolution de ton écran au démarrage. Redémarre après un changement de résolution ou de mise à l'échelle Windows. |

> **À savoir** : l'interface n'a qu'un mode sombre. Le bouton clair/sombre des
> versions précédentes a été retiré.
