# Les Ateliers Doublage — Raspberry Pi 400

🎬 **Générateur de vidéos SYNC autonome pour Raspberry Pi 400**

Portage dédié et optimisé pour ARM64 (Raspberry Pi OS).

## ✨ Features

- ✅ Générateur vidéo SYNC CLI
- ✅ Batch processing (traiter plusieurs vidéos)
- ✅ Léger et autonome (pas de dépendances macOS)
- ✅ Installation automatisée
- ✅ Support ARM64 natif

## 🚀 Installation rapide

### Sur Raspberry Pi 400

```bash
# Récupérer le code
git clone <votre-repo-pi400> ~/AD-Pi400
cd ~/AD-Pi400

# Lancer l'installer
chmod +x install.sh
./install.sh
```

L'installer fait tout automatiquement :
- ✓ Dépendances système (FFmpeg, Python, etc)
- ✓ Environnement virtuel Python
- ✓ Packages Python (numpy, pandas, moviepy, etc)
- ✓ Structure de répertoires
- ✓ Tests de vérification

**Temps** : 30-60 minutes sur Pi 400 (compilation ARM64 des packages)

## 📋 Structure du projet

```
AD-Pi400/
├── install.sh              # Installer automatisé
├── uninstall.sh            # Désinstallation propre
├── README.md               # Ce fichier
├── RASPBERRY_PI_400.md     # Guide détaillé
│
├── server.py               # API web (optionnel)
├── generate_sync.py        # Générateur vidéo SYNC
├── batch_sync.py           # Traiter plusieurs vidéos
├── requirements.txt        # Dépendances Python
├── FPS.txt                 # Configuration FPS
│
├── VIDEOS/                 # 📁 Vidéos d'entrée
├── SCRIPTS/                # 📁 Scripts Excel
├── VI/                     # 📁 Audio de référence
└── VIDEOS/SYNC/            # 📁 Vidéos générées
```

## 🎯 Utilisation

### Générer UNE vidéo SYNC

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Générer une vidéo avec un script
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx

# Résultat : VIDEOS/SYNC/video_Sync.mp4
```

### Traiter TOUTES les vidéos

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Générer toutes les vidéos (sauf les existantes)
python3 batch_sync.py

# Forcer la régénération
python3 batch_sync.py --force
```

## ⚙️ Configuration

### FPS (images par seconde)

Éditer `FPS.txt` :
```
50
```

Valeurs suggérées :
- `25` : rapide (test)
- `30` : équilibre
- `50` : qualité haute (lent)

### Chemins personnalisés

Créer `~/AD-Pi400/config.json` :
```json
{
  "videos_dir": "/home/pi/AD-Pi400/VIDEOS",
  "scripts_dir": "/home/pi/AD-Pi400/SCRIPTS",
  "vi_dir": "/home/pi/AD-Pi400/VI",
  "repartition_csv": "/home/pi/AD-Pi400/repartition.csv"
}
```

## 📊 Performance

Sur **Raspberry Pi 400** (4 cœurs ARM64, 4-8 GB RAM) :

| Durée | Résolution | FPS | Temps |
|-------|-----------|-----|-------|
| 1 min | 1280x720  | 25  | 2-3 min |
| 1 min | 1280x720  | 50  | 4-6 min |
| 5 min | 1280x720  | 25  | 10-15 min |

Mémoire utilisée : ~300-500 MB

## 🔧 Dépannage

### Python : "No module named X"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### FFmpeg : "command not found"
```bash
sudo apt install ffmpeg
```

### Lenteur / "Out of memory"
- Réduire `OUTPUT_W, OUTPUT_H` dans `generate_sync.py`
- Réduire `FPS` dans `FPS.txt`
- Traiter des vidéos plus courtes

### Processus gelé
```bash
source venv/bin/deactivate
source venv/bin/activate
```

## 📚 Documentation

- [RASPBERRY_PI_400.md](./RASPBERRY_PI_400.md) — Guide détaillé d'installation
- [CERTBOT.md](./CERTBOT.md) — HTTPS avec Let's Encrypt (optionnel)

## 🛠️ Désinstallation

```bash
cd ~/AD-Pi400
./uninstall.sh
```

## 📦 Contenu du package

Ce repo contient **uniquement les éléments ARM Pi** :
- ✅ Scripts Python (cœur du programme)
- ✅ Installer et dépendances
- ✅ Docs d'installation
- ❌ App native macOS (pas pertinent)
- ❌ Installeur .pkg macOS (pas pertinent)

## 🔄 Workflow collaboratif

Différents repos pour différentes plateformes :

| Plateforme | Repo | État |
|-----------|------|------|
| **macOS** | `AD` | ✅ App native + serveur web |
| **ARM Pi 400** | `AD-Pi400` | ✅ CLI autonome |
| Autres Pi/Linux | À adapter | 🔄 En cours |

Chaque repo est optimisé pour sa plateforme.

## 🤝 Support

Pour les questions ou problèmes :
1. Vérifier [RASPBERRY_PI_400.md](./RASPBERRY_PI_400.md)
2. Vérifier les logs : `~/AD-Pi400/install.log`
3. Tester : `python3 generate_sync.py --help`

## 📄 Licence

À définir (même que le projet original)

---

**Version** : 1.0  
**Dernière mise à jour** : Nov 2026  
**Testé sur** : Raspberry Pi 400 avec Raspberry Pi OS 64-bit
