# Structure du projet AD-Pi400

## Vue d'ensemble

Repo **ARM Pi 400 dédié** pour **Les Ateliers Doublage**.

Dépôt parent (macOS) : https://github.com/tanais-arts/AD

## Architecture

```
AD-Pi400/
│
├── 📄 Documentation
│   ├── README.md                 ← Démarrage rapide
│   ├── RASPBERRY_PI_400.md       ← Guide détaillé
│   └── STRUCTURE.md              ← Ce fichier
│
├── 🚀 Installation & Setup
│   ├── install.sh                ← Installer automatisé (ARM64)
│   ├── uninstall.sh              ← Désinstallation propre
│   └── requirements.txt           ← Dépendances Python
│
├── 🐍 Code source
│   ├── server.py                 ← API web (optionnel)
│   ├── generate_sync.py          ← Générateur vidéo SYNC
│   ├── batch_sync.py             ← Batch processing
│   ├── debug_match.py            ← Utilitaires de débogage
│   ├── normalize_scripts.py       ← Normalisation scripts
│   └── syllable_count.py          ← Compteur de syllabes
│
├── ⚙️ Configuration
│   ├── FPS.txt                   ← Framerate (modifiable)
│   ├── config.json               ← Chemins personnalisés (généré)
│   └── repartition.csv           ← Catalogue vidéos (généré)
│
├── 📁 Répertoires de données (créés par installer)
│   ├── VIDEOS/                   ← Vidéos d'entrée
│   ├── SCRIPTS/                  ← Scripts Excel/ODS/CSV
│   ├── VI/                       ← Audio de référence
│   ├── VIDEOS/SYNC/              ← Vidéos SYNC générées
│   ├── GENERATED/                ← Fichiers générés (détx)
│   └── logs/                     ← Fichiers de log
│
└── 🐍 Environnement (créé par installer)
    └── venv/                     ← Environnement virtuel Python
        ├── bin/python3           ← Python executable
        └── lib/python*/site-packages/  ← Packages
```

## Cycle de vie

### Installation (une fois)
```bash
./install.sh
```

### Utilisation (répétée)
```bash
cd ~/AD-Pi400
source venv/bin/activate
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
```

### Désinstallation (nettoyage)
```bash
./uninstall.sh
```

## Fichiers critiques

| Fichier | Rôle | Modifiable ? | Sauvegarde requise ? |
|---------|------|-------------|-------------------|
| `generate_sync.py` | Cœur du générateur | ❌ Non | ✓ Oui |
| `batch_sync.py` | Batch processing | ❌ Non | ✓ Oui |
| `requirements.txt` | Dépendances | ⚠️ Rarement | ✓ Oui |
| `FPS.txt` | Configuration FPS | ✅ Oui | ❌ Non |
| `config.json` | Chemins | ✅ Oui | ❌ Non |
| `VIDEOS/` | Données utilisateur | ✅ Oui | ✓ Oui |
| `SCRIPTS/` | Données utilisateur | ✅ Oui | ✓ Oui |
| `VIDEOS/SYNC/` | Résultats générés | ✅ Oui | ✓ Oui |

## Versioning

### Tags

- `v1.0` — Version initiale (ARM64)
- `v1.1` — Optimisations ARM64
- etc.

### Branches

- `main` — Version stable (production)
- `develop` — Développement (tests)
- `feature/*` — Nouvelles features
- `hotfix/*` — Corrections urgentes

## Différences avec AD (macOS)

| Aspect | AD (macOS) | AD-Pi400 (ARM) |
|--------|-----------|---------------|
| **Plateforme** | macOS x86_64 + Apple Silicon | Raspberry Pi OS ARM64 |
| **App native** | Swift GUI | ❌ CLI seulement |
| **Web UI** | Flask/Gunicorn | Optionnel |
| **Installer** | .pkg (macOS) | Bash script (Linux) |
| **Optimisations** | Intel/ARM64 natives | ARM64 seulement |
| **Configuration** | LaunchAgent | Systemd/cron |
| **Dépendances** | Binaires x86_64 | Compilées ARM64 |

## Dépendances externes

### Système (installées par `install.sh`)
- FFmpeg (video encoding)
- Python3 + pip
- build-essential (compilation)
- Dépendances mathématiques (numpy, scipy stack)

### Python (dans requirements.txt)
```
gunicorn
Flask
numpy==1.26.4
pandas
Pillow
moviepy
imageio_ffmpeg
openpyxl
odfpy
xlrd
gevent
packaging
pyphen
```

## Workflow collaboratif

### Mettre à jour AD-Pi400

```bash
cd ~/AD-Pi400
git add .
git commit -m "Description des changements"
git push origin main
```

### Fusionner depuis AD (macOS)

```bash
# Vérifier les changements du repo AD
git remote add upstream https://github.com/tanais-arts/AD.git
git fetch upstream

# Fusionner sélectivement
git cherry-pick <commit>  # Ou merge si changements compatibles
```

## Déploiement

### Sur un nouveau Pi 400

```bash
git clone https://github.com/tanais-arts/AD-Pi.git ~/AD-Pi400
cd ~/AD-Pi400
./install.sh
```

### Mise à jour

```bash
cd ~/AD-Pi400
git pull origin main
# Dépendances Python mises à jour automatiquement au redémarrage du serveur
```

## Performance & Limitations

### Limitations matérielles (Pi 400)

- **CPU** : 4 cœurs ARM @ 1.8 GHz (pas parallélisable)
- **RAM** : 4-8 GB (limité pour vidéos HD)
- **Stockage** : SD card (lent) ou USB 3.0 (recommandé)
- **Encodage vidéo** : Pas d'accélération hardware GPU

### Optimisations implémentées

- Compilation ARM64 native (pas d'émulation)
- Venv isolé (pas de conflicts)
- FPS configurable (pour adapter au hardware)
- Batch processing séquentiel (pas de parallélisme)

## Roadmap future

- [ ] Support GPU (si disponible)
- [ ] Parallélismes batch (multiple workers)
- [ ] Cache de calculs (pour vidéos similaires)
- [ ] API REST allégée
- [ ] Web UI légère (optionnel)
- [ ] Systemd service pour démarrage auto

---

**Repository** : https://github.com/tanais-arts/AD-Pi  
**Parent** : https://github.com/tanais-arts/AD  
**Last updated** : Nov 2026
