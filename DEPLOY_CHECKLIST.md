# Checklist de déploiement sur Raspberry Pi 400

## Avant le premier déploiement

### Sur votre Mac (cette machine)

- [x] Workspace séparé créé : `/Users/tanaismusic/Documents/AD-Pi400/`
- [x] Repo Git local initialisé
- [x] Remote GitHub ajouté : `https://github.com/tanais-arts/AD-Pi.git`
- [x] Commit initial créé
- [x] Fichiers essentiels copiés depuis AD
- [x] Documentation rédigée (README, RASPBERRY_PI_400.md)
- [x] Scripts d'installation créés (install.sh, uninstall.sh)
- [ ] **À FAIRE : Pousser vers GitHub** → `git push -u origin main`

### Commande pour pousser

```bash
cd /Users/tanaismusic/Documents/AD-Pi400
git push -u origin main
```

## Après le push GitHub

### Sur Raspberry Pi 400 (première installation)

```bash
# 1. Se connecter au Pi
ssh pi@raspberrypi.local

# 2. Cloner le repo
git clone https://github.com/tanais-arts/AD-Pi.git ~/AD-Pi400
cd ~/AD-Pi400

# 3. Lancer l'installer
chmod +x install.sh
./install.sh
# → Prend 30-60 min (compilation ARM64)

# 4. Vérifier l'installation
source venv/bin/activate
python3 generate_sync.py --help
```

## Test initial sur Pi 400

```bash
# 1. Copier une vidéo de test (courte, <30 sec)
scp ~/test.mp4 pi@raspberrypi.local:~/AD-Pi400/VIDEOS/

# 2. Copier un script de test
scp ~/test.xlsx pi@raspberrypi.local:~/AD-Pi400/SCRIPTS/

# 3. Générer la sync
ssh pi@raspberrypi.local
cd ~/AD-Pi400
source venv/bin/activate
python3 generate_sync.py VIDEOS/test.mp4 SCRIPTS/test.xlsx

# 4. Récupérer le résultat
scp pi@raspberrypi.local:~/AD-Pi400/VIDEOS/SYNC/test_Sync.mp4 ~/Downloads/

# 5. Regarder le fichier généré
```

## Mise à jour sur Pi 400 (futur)

```bash
cd ~/AD-Pi400
git pull origin main
# Les dépendances Python sont inutiles si rien n'a changé
```

## Déploiement sur d'autres Pi 400

```bash
# Même processus que "première installation"
git clone https://github.com/tanais-arts/AD-Pi.git ~/AD-Pi400
cd ~/AD-Pi400
./install.sh
```

## Points de contrôle

- [ ] Repo poussé vers GitHub
- [ ] Clone depuis GitHub fonctionne
- [ ] install.sh exécutable et complet
- [ ] Première vidéo générée sur Pi 400
- [ ] Résultat récupéré et vérifié
- [ ] Documentation à jour sur GitHub

## Troubleshooting

### Si le push échoue

```bash
# Vérifier l'authentification
gh auth status

# Ou utiliser SSH
git remote set-url origin git@github.com:tanais-arts/AD-Pi.git
git push -u origin main
```

### Si l'install sur Pi 400 échoue

```bash
# Vérifier les logs
cat ~/AD-Pi400/install.log | tail -50

# Relancer le script
cd ~/AD-Pi400
./install.sh
```

### Si la génération vidéo échoue sur Pi 400

```bash
# Vérifier FFmpeg
ffmpeg -version

# Vérifier l'espace disque
df -h

# Vérifier la RAM
free -h

# Réessayer avec une vidéo plus courte
```

## Prochaines étapes

1. ✅ Pousser vers GitHub
2. ✅ Tester sur Pi 400
3. ⏳ Distribuer le lien GitHub aux autres utilisateurs
4. ⏳ Collecter les retours
5. ⏳ Ajouter des optimisations si besoin

---

**Status** : 🟡 En attente de push vers GitHub  
**Last update** : Nov 13, 2026
