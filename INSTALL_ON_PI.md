# Installation sur Raspberry Pi 400 — Guide étape par étape

## Prérequis

- Raspberry Pi 400 avec Raspberry Pi OS 64-bit (Bullseye ou Bookworm)
- Accès SSH ou terminal local
- Connexion Internet
- ~20 GB d'espace disque libre

## Installation rapide (3 étapes)

### ÉTAPE 1 : Cloner le repo GitHub

```bash
ssh pi@raspberrypi.local
```

Ou directement sur le Pi avec un terminal.

Puis :
```bash
cd ~
git clone https://github.com/tanais-arts/AD-Pi.git AD-Pi400
cd AD-Pi400
```

**Résultat attendu** :
```
Cloning into 'AD-Pi400'...
remote: Enumerating objects: 20, done.
...
```

### ÉTAPE 2 : Lancer l'installer

```bash
chmod +x install.sh
./install.sh
```

**L'installer va :**
- Vérifier que c'est un Pi 400 ARM64
- Mettre à jour les paquets
- Installer FFmpeg et dépendances
- Créer l'environnement Python
- Installer les packages Python (le plus long)
- Tester et afficher un résumé

**Durée : 45-60 minutes** (patience, c'est normal !)

**Vous verrez :**
```
╔════════════════════════════════════════════╗
║  Installation — Les Ateliers Doublage     ║
╚════════════════════════════════════════════╝

Vérification de l'environnement...
✓ Python3 3.11 trouvé
✓ Raspberry Pi 400 détecté

[ÉTAPE 1] Dépendances système...
[ÉTAPE 2] Structure de répertoires...
[ÉTAPE 3] Copie du programme...
[ÉTAPE 4] Environnement virtuel Python...
[ÉTAPE 5] Packages Python (peut prendre 30-60 min)
  ⏳ Patientez... numpy et pandas se compilent (normal)
[ÉTAPE 6] Configuration...
[ÉTAPE 7] Scripts de lancement...
[ÉTAPE 8] Tests...

✅ INSTALLATION TERMINÉE !
```

### ÉTAPE 3 : Vérifier l'installation

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Tester un import
python3 -c "import numpy; print('✓ numpy OK')"

# Tester FFmpeg
ffmpeg -version | head -1

# Voir l'aide
python3 generate_sync.py --help
```

**Résultat attendu** :
```
✓ numpy OK
ffmpeg version 4.4.2-1~rpi0 ...
Usage:
  python generate_sync.py <video> <script> [output.mp4]
```

---

## 🎯 Première vidéo SYNC (test)

### Copier une vidéo et un script de test

Depuis votre Mac (sur votre machine locale) :

```bash
# Copier une vidéo test vers le Pi
scp ~/vidéo_test.mp4 pi@raspberrypi.local:~/AD-Pi400/VIDEOS/

# Copier un script test
scp ~/script_test.xlsx pi@raspberrypi.local:~/AD-Pi400/SCRIPTS/
```

Ou manuellement sur le Pi :
```bash
# Copier depuis une clé USB ou partage réseau
cp /mnt/usb/video.mp4 ~/AD-Pi400/VIDEOS/
cp /mnt/usb/script.xlsx ~/AD-Pi400/SCRIPTS/
```

### Générer la vidéo SYNC

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Générer la sync
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
```

**En cours** (vous verrez la progression) :
```
[AD] Génération... phase: detect ...
[AD] Génération... phase: render (progress: 25%)
[AD] Génération... phase: render (progress: 50%)
...
✓ Vidéo générée : VIDEOS/SYNC/video_Sync.mp4
```

**Résultat** :
```
~/AD-Pi400/VIDEOS/SYNC/video_Sync.mp4
```

### Récupérer le fichier (sur votre Mac)

```bash
scp pi@raspberrypi.local:~/AD-Pi400/VIDEOS/SYNC/video_Sync.mp4 ~/Downloads/
```

Puis regarder le fichier dans `~/Downloads/`

---

## 📋 Commandes utiles

### Activer l'environnement (avant chaque utilisation)

```bash
cd ~/AD-Pi400
source venv/bin/activate
```

### Générer une vidéo

```bash
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
```

### Générer toutes les vidéos

```bash
python3 batch_sync.py
```

### Désactiver l'environnement

```bash
deactivate
```

### Regarder les logs d'installation

```bash
cat ~/AD-Pi400/install.log
```

### Vérifier l'espace disque

```bash
df -h
du -sh ~/AD-Pi400/
```

### Arrêter un traitement (Ctrl+C)

```bash
Ctrl + C
```

---

## 🔧 Dépannage

### ❌ "command not found: git"

```bash
sudo apt install git
```

### ❌ "git clone échoue"

Vérifier la connexion Internet :
```bash
ping github.com
```

### ❌ "Permission denied" sur install.sh

```bash
chmod +x ~/AD-Pi400/install.sh
```

### ❌ "No module named numpy" après installation

```bash
cd ~/AD-Pi400
source venv/bin/activate
pip install -r requirements.txt
```

### ❌ "FFmpeg not found"

```bash
sudo apt install ffmpeg
```

### ❌ "Out of memory" pendant la génération

Réduire la résolution ou FPS :
1. Éditer `~/AD-Pi400/FPS.txt` (mettre 25 au lieu de 50)
2. Ou éditer `generate_sync.py` et réduire OUTPUT_W/OUTPUT_H
3. Réessayer avec une vidéo plus courte

### ❌ L'installation est très lente

C'est normal ! NumPy et Pandas se compilent :
- Laissez tourner (peut prendre 60+ min)
- Vérifier avec `top` que le CPU travaille

---

## ✅ Checklist de vérification

Après l'installation :

- [ ] `cd ~/AD-Pi400` — OK
- [ ] `source venv/bin/activate` — OK
- [ ] `python3 generate_sync.py --help` — OK
- [ ] `ffmpeg -version` — OK
- [ ] `ls VIDEOS/ SCRIPTS/ VI/` — OK
- [ ] Première vidéo générée — OK

Si tout est ✓, c'est bon !

---

## 🚀 Workflow quotidien

```bash
# Chaque fois que vous voulez générer une vidéo :

ssh pi@raspberrypi.local              # Se connecter
cd ~/AD-Pi400                         # Aller dans le répertoire
source venv/bin/activate             # Activer l'env

python3 generate_sync.py \           # Générer
  VIDEOS/ma_video.mp4 \
  SCRIPTS/mon_script.xlsx

# Récupérer le fichier sur Mac :
# scp pi@raspberrypi.local:~/AD-Pi400/VIDEOS/SYNC/ma_video_Sync.mp4 ~/Downloads/
```

---

## 📞 Support

Si vous avez un problème :

1. **Vérifier les logs** :
   ```bash
   cat ~/AD-Pi400/install.log | tail -100
   ```

2. **Relancer l'installer** :
   ```bash
   cd ~/AD-Pi400
   ./install.sh
   ```

3. **Chercher dans la doc** :
   - README.md
   - RASPBERRY_PI_400.md

---

**Installation complétée ? Vous êtes prêt à générer des vidéos SYNC ! 🎬**
