# Media Batch Converter

Convertisseur batch images → WebP ([(Node.js](https://nodejs.org/) + [sharp](https://sharp.pixelplumbing.com)) et vidéos → MP4/WebM ([Python](https://www.python.org) + [ffmpeg](https://ffmpeg.org)), avec parallélisation, normalisation des noms et rapports de compression

## Sommaire

- [Media Batch Converter](#media-batch-converter)
  - [Sommaire](#sommaire)
  - [Description](#description)
  - [Fonctionnalités](#fonctionnalités)
    - [Images (image\_converter)](#images-image_converter)
    - [Vidéos (video\_converter)](#vidéos-video_converter)
  - [Prérequis](#prérequis)
  - [Installation](#installation)
    - [Mac](#mac)
    - [Linux](#linux)
    - [Windows](#windows)
  - [Utilisation rapide](#utilisation-rapide)
    - [Images → WebP (Node + sharp)](#images--webp-node--sharp)
    - [Vidéos → MP4/WebM (Python + ffmpeg)](#vidéos--mp4webm-python--ffmpeg)
  - [Fonctionnement](#fonctionnement)
  - [Détails — Images (Sharp)](#détails--images-sharp)
  - [Détails — Vidéos (FFmpeg)](#détails--vidéos-ffmpeg)
  - [Paramètres \& personnalisation](#paramètres--personnalisation)
  - [Debug](#debug)

## Description

- Images : encode en WebP avec qualité équilibrée, traitement multi-cœurs, logs par fichier + bilan.
- Vidéos : génère MP4 (H.264/AAC) et WebM (VP9/Opus), bitrate cible dynamique (plafond taille), réessai si WebM trop lourd.

## Fonctionnalités

### Images (image_converter)

- Entrées : .jpg, .jpeg, .png, .gif, .webp, .avif, .tiff
- Sortie : WebP (qualité 80, effort 4)
- Parallélisation via worker_threads
- Slugification des noms de fichiers (minuscules, espaces → -, caractères spéciaux supprimés)
- Rapport par fichier et bilan global (taille originale vs WebP)

### Vidéos (video_converter)

- Entrées : .mp4, .mov, .m4v, .avi, .mkv, .webm
- Sorties : MP4 (H.264/AAC) + WebM (VP9/Opus)
- Parallélisation via ProcessPoolExecutor
- Probe auto (width/height/duration) via ffprobe
- Bitrate cible dynamique en fonction de la durée, avec plafond de 12 MB par fichier (visé)
- Faststart MP4, espace colorimétrique BT.709, et bilan global (ratios)

## Prérequis

- [Node.js](https://nodejs.org/) ≥ 18
- [sharp](https://sharp.pixelplumbing.com) nécessite un environnement Node moderne (libvips est géré par le module).

```bash
node -v
npm -v
```

- [Python](https://www.python.org) ≥ 3.9

```bash
python3 --version
```

- [FFmpeg](https://ffmpeg.org) (incluant [ffprobe](https://ffmpeg.org/ffprobe.html)) dans le PATH

```bash
ffmpeg -version
ffprobe -version
```

## Installation

### Mac

Avec [Homebrew](https://brew.sh) :

```bash
brew install ffmpeg python node
```

### Linux

Avec [apt](https://ubuntu.com/tutorials/how-to-install-and-use-docker#1-overview) :

```bash
sudo apt update
sudo apt install -y ffmpeg python3 nodejs
```

### Windows

Installe [FFmpeg](https://ffmpeg.org/download.html), [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/) ([Chocolatey](https://chocolatey.org/), [winget](https://winget.run/), ou installateurs officiels), puis ajoute FFmpeg au PATH.

Avec [Chocolatey](https://chocolatey.org/) :

```bash
choco install ffmpeg
choco install python
choco install nodejs
```

## Utilisation rapide

### Images → WebP (Node + sharp)

A venir

### Vidéos → MP4/WebM (Python + ffmpeg)

```python
python3 video_converter.py
```

- Entrée : videos_input/*
- Sorties : videos_output/mp4/*.mp4 et videos_output/webm/*.webm

## Fonctionnement

Vous devez placer vos fichiers dans les dossiers appropriés (images_input / videos_input) avant de lancer les scripts.
Les vidéos converties seront dans dossiers de images_output et videos_output.

```bash
git clone git@github.com:MatteoCourquin/COMPRESSOR.git # Si vous n'utilisez pas SSH, utilisez l'URL adapté
cd COMPRESSOR

# Images
# Placer vos images dans images_input
cd images_input
python3 image_converter.py
# Les images converties seront dans images_output

# Vidéos
# Placer vos vidéos dans videos_input
cd videos_input
python3 video_converter.py
# Les vidéos converties seront dans videos_output
```

## Détails — Images (Sharp)

Algorithme :

- Parcours du dossier images_input
- Filtrage des extensions supportées
- Workers en parallèle (≈ CPU - 1)
- Pour chaque image :
  - génération d’un nom normalisé (formatFilename)
  - encodage WebP (quality: 80, effort: 4, lossless: false, nearLossless: false)
  - calcul KB avant/après & logs
- Résumé global : nombre OK/KO, tailles cumulées & ratio

Personnalisation rapide :
Dans `images_converter.py`, ajuster les paramétres suivants :

- Qualité WebP : `quality: 80`
- Effort : `effort: 4`
- Dossiers : `INPUT_DIR`, `OUTPUT_DIR`

## Détails — Vidéos (FFmpeg)

Pipeline :

- Probe avec ffprobe (dimensions + durée)
- Bitrate cible calculé par calculate_target_bitrate(duration)
  - base 3 Mbps
  - objectif de ~0,2 MB/s avec plafond 12 MB par fichier
- MP4 (H.264) :
  - `-crf 20`, `-preset medium`, `-profile:v main`, `-level 4.0`
  - `-maxrate target_bitrate`, `-bufsize 2×`
  - `-movflags` +faststart, couleurs BT.709
  - Audio aac 128k / 48 kHz
- WebM (VP9) :
  - cible ≈ 0,9× target_bitrate, garde-fous min/maxrate
  - `-speed 1`, `-tile-columns 2`, `-lag-in-frames 25`, `-g 240`
  - Audio opus 96k
  - Si WebM > MP4, retente avec bitrate réduit
- Résumé global : tailles cumulées & ratios

Parallélisation : max_workers = CPU - 1

Personnalisation rapide

Dans `video_converter.py`, ajuste :

- Politique de bitrate : calculate_target_bitrate
- Qualité MP4 : `-crf`, `-preset`
- Qualité WebM : `-b:v`, `-speed`, etc.
- Dossiers : `INPUT_DIR`, `OUTPUT_DIR`

## Paramètres & personnalisation

| Zone   | Paramètre                | Fichier             | Valeur par défaut            | Effet                                   |
| ------ | ------------------------ | ------------------- | ---------------------------- | --------------------------------------- |
| Images | quality                  | image_converter.py | 80                           | Qualité WebP (0–100)                    |
| Images | effort                   | image_converter.py | 4                            | Temps d’optimisation (0–6)              |
| Images | INPUT_DIR / OUTPUT_DIR   | image_converter.mjs | images_input / images_output | Dossiers E/S                            |
| Vidéos | calculate_target_bitrate | video_converter.py  | min(3 Mbps, 0,2 MB/s)        | Contrôle la taille visée                |
| Vidéos | MP4 –crf                 | video_converter.py  | 20                           | Qualité/poids H.264 (↓ mieux = ↑ poids) |
| Vidéos | WebM –speed              | video_converter.py  | 1                            | Qualité/temps d’encodage VP9            |
| Vidéos | INPUT_DIR / OUTPUT_DIR   | video_converter.py  | videos_input / videos_output | Dossiers E/S                            |

## Debug

- “Aucun fichier vidéo supporté…” : tes fichiers ne sont pas à la racine de videos_input/ ou extensions non supportées. Le script n’est pas récursif par défaut.
- ffmpeg/ffprobe introuvable : installe FFmpeg et vérifie le PATH.
- CPU à 100 % : baisse max_workers (batch) et/ou ffmpeg_threads.
