# Installation et utilisation — Raspberry Pi 400

Guide détaillé pour installer et utiliser **Les Ateliers Doublage** sur Raspberry Pi 400.

## Prérequis

- **Raspberry Pi 400** avec Raspberry Pi OS 64-bit (Bullseye ou Bookworm)
- Connexion Internet (pour télécharger les packages)
- ~20 GB d'espace disque libre (pour l'installation + données)
- Accès utilisateur `pi` ou équivalent

## Installation automatisée

### Étape 1 : Récupérer le code

Sur votre Mac :
```bash
# Cloner le repo Pi400
git clone https://github.com/tanais-arts/AD-Pi.git ~/AD-Pi

# Copier sur le Pi (via USB, rsync, ou directement si vous avez le repo sur le Pi)
scp -r ~/AD-Pi pi@raspberrypi.local:~/AD-Pi400
```

Ou directement sur le Pi :
```bash
ssh pi@raspberrypi.local
git clone https://github.com/tanais-arts/AD-Pi.git ~/AD-Pi400
```

### Étape 2 : Lancer l'installer

```bash
cd ~/AD-Pi400
chmod +x install.sh
./install.sh
```

L'installer va :
- ✓ Installer FFmpeg et les dépendances système
- ✓ Créer un environnement Python virtuel
- ✓ Installer tous les packages Python (numpy, pandas, moviepy, etc)
- ✓ Préparer la structure de répertoires (VIDEOS, SCRIPTS, VI)
- ✓ Tester les installations

**Durée** : 30-60 minutes (la compilation ARM64 est lente, c'est normal)

### Résultat

```
Installation directory: /home/pi/AD-Pi400
✓ VIDEOS/             — Vidéos d'entrée
✓ SCRIPTS/            — Scripts Excel
✓ VI/                 — Audio de référence
✓ VIDEOS/SYNC/        — Vidéos générées
✓ venv/               — Environnement Python
```

## Utilisation

### Générer une vidéo SYNC unique

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Générer la sync
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx

# Ou avec un chemin de sortie personnalisé
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx VIDEOS/SYNC/custom_output.mp4
```

**Résultat** : `VIDEOS/SYNC/video_Sync.mp4`

### Traiter plusieurs vidéos (batch)

```bash
cd ~/AD-Pi400
source venv/bin/activate

# Générer toutes les vidéos manquantes
python3 batch_sync.py

# Régénérer TOUTES les vidéos (même si elles existent)
python3 batch_sync.py --force
```

Le script :
1. Parcourt `VIDEOS/` pour trouver les vidéos `.mp4`
2. Cherche un script `SCRIPTS/<video_name>.xlsx`
3. Génère `VIDEOS/SYNC/<video_name>_Sync.mp4`
4. Affiche les résultats

## Configuration

### FPS (images par seconde)

Éditer `~/AD-Pi400/FPS.txt` :
```
50
```

Valeurs recommandées :
- `25` : rapide (test/démo)
- `30` : équilibre qualité/vitesse
- `50` : haute qualité (plus lent)

### Chemins personnalisés

Créer `~/AD-Pi400/config.json` :
```json
{
  "videos_dir": "/home/pi/AD-Pi400/VIDEOS",
  "scripts_dir": "/home/pi/AD-Pi400/SCRIPTS",
  "vi_dir": "/home/pi/AD-Pi400/VI",
  "repartition_csv": "/home/pi/AD-Pi400/repartition.csv",
  "port": "1348"
}
```

## Workflow réel

### Étape 1 : Copier vidéo et script sur le Pi

```bash
# Depuis votre Mac
scp video.mp4 script.xlsx pi@raspberrypi.local:~/AD-Pi400/

# Depuis le Pi, les mettre au bon endroit
mv ~/video.mp4 ~/AD-Pi400/VIDEOS/
mv ~/script.xlsx ~/AD-Pi400/SCRIPTS/
```

### Étape 2 : Générer la sync

```bash
ssh pi@raspberrypi.local
cd ~/AD-Pi400
source venv/bin/activate
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
```

### Étape 3 : Récupérer le résultat

```bash
# Depuis votre Mac
scp pi@raspberrypi.local:~/AD-Pi400/VIDEOS/SYNC/video_Sync.mp4 ~/Downloads/
```

## Performance

### Temps de génération sur Pi 400

| Durée vidéo | Résolution | FPS | Temps estime |
|-------------|-----------|-----|-------------|
| 1 minute | 1280x720 | 25 | 2-3 min |
| 1 minute | 1280x720 | 50 | 4-6 min |
| 5 minutes | 1280x720 | 25 | 10-15 min |
| 1 minute | 960x540 | 50 | 1-2 min |

### Ressources utilisées

- **CPU** : 3-4 cœurs (sur 4 disponibles)
- **RAM** : 300-500 MB
- **Disque** : environ 1 Go par minute de vidéo 1280x720

## Dépannage

### "No module named X"

```bash
cd ~/AD-Pi400
source venv/bin/activate
pip install -r requirements.txt
```

### "FFmpeg not found"

```bash
sudo apt install ffmpeg
```

### Vidéo incomplète ou fichier vide

1. Vérifier que la vidéo source est valide
2. Regarder les logs stderr (messages d'erreur)
3. Réduire FPS ou résolution et réessayer

### Processus tue après plusieurs vidéos

```bash
# Désactiver et réactiver le venv
source venv/bin/deactivate
source venv/bin/activate

# Relancer
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
```

### "Out of memory"

Réduire `OUTPUT_W` et `OUTPUT_H` dans `generate_sync.py` (lignes ~30) :

```python
# De
OUTPUT_W, OUTPUT_H = 1280, 720

# À
OUTPUT_W, OUTPUT_H = 960, 540  # 4x moins rapide
```

Puis relancer la génération.

### Vitesse très lente

1. Vérifier que vous n'utilisez pas `--force` avec batch_sync.py
2. Arrêter les autres processus (htop pour voir)
3. Réduire `FPS` dans FPS.txt
4. Vérifier la température du CPU (peut être limitée thermiquement)

```bash
# Vérifier CPU/RAM/températures
vcgencmd measure_temp
top
```

## Automatisation (optionnel)

### Générer vidéos chaque nuit

Ajouter dans crontab :

```bash
crontab -e
```

Ajouter :
```cron
# Générer toutes les vidéos à 2h du matin chaque jour
0 2 * * * cd ~/AD-Pi400 && source venv/bin/activate && python3 batch_sync.py >> ~/AD-Pi400/logs/batch.log 2>&1
```

### Supprimer les vieilles vidéos SYNC

```bash
# Supprimer les SYNC générées il y a plus de 7 jours
find ~/AD-Pi400/VIDEOS/SYNC -name "*_Sync.mp4" -mtime +7 -delete
```

## Désinstallation

```bash
cd ~/AD-Pi400
./uninstall.sh
```

Cela va :
- ✓ Supprimer l'environnement virtuel Python
- ✓ Supprimer les fichiers de code
- ✓ Nettoyer les fichiers temporaires
- ✗ CONSERVER les répertoires VIDEOS, SCRIPTS, VI et repartition.csv

Pour une suppression complète :
```bash
rm -rf ~/AD-Pi400
```

## Conseils pour l'utilisation

1. **Vérifier l'espace disque** avant d'importer beaucoup de vidéos
   ```bash
   df -h
   ```

2. **Monitorer la chaleur** du Pi lors de la génération (surtout si FPS=50)
   ```bash
   watch vcgencmd measure_temp
   ```

3. **Garder des backups** des vidéos SYNC importants
   ```bash
   tar -czf SYNC_backup_$(date +%Y%m%d).tar.gz VIDEOS/SYNC/
   ```

4. **Mettre à jour régulièrement** si vous avez le repo Git
   ```bash
   cd ~/AD-Pi400
   git pull
   ```

## Ressources

- [Raspberry Pi OS Documentation](https://www.raspberrypi.com/documentation/)
- [Python Documentation](https://docs.python.org/3/)
- [moviepy Documentation](https://zulko.github.io/moviepy/)
- [FFmpeg Guide](https://ffmpeg.org/)

## Logs et débogage

Les logs d'installation sont dans :
```
~/AD-Pi400/install.log
```

Pour activer le mode verbose pendant la génération :
```bash
python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx 2>&1 | head -50
```

## Questions fréquentes

**Q: Puis-je accélérer la génération ?**  
R: Réduire FPS, résolution, ou durée vidéo. Pi 400 a des limites matérielles.

**Q: Comment transférer vidéos/scripts rapidement ?**  
R: Utiliser rsync sur le réseau, ou une clé USB externe.

**Q: Puis-je générer plusieurs vidéos en parallèle ?**  
R: Non recommandé. Pi 400 n'a que 4 cœurs et RAM limitée. Faire du batch séquentiel.

**Q: Comment garder les vidéos sync entre démarrages ?**  
R: Elles sont dans `VIDEOS/SYNC/` qui persiste. Ne pas supprimer ce répertoire.

---

**Version** : 1.0  
**Dernière mise à jour** : Nov 2026  
**Testé sur** : Raspberry Pi 400 avec Raspberry Pi OS 64-bit (Bullseye & Bookworm)
