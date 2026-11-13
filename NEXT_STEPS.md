# 🚀 Prochaines Étapes — AD-Pi400

## ✅ Phase 1 : Configuration Immédiate (COMPLÉTÉE)

- ✅ Installation de l'application
- ✅ Configuration des permissions
- ✅ Création des fichiers CSV
- ✅ Documentation complète
- ✅ Préparation des commits Git

**Status:** 🟢 **TERMINÉ**

---

## 🔄 Phase 2 : Push vers GitHub (À FAIRE)

### Étape 1 : Authentification GitHub

**Option A - Personal Access Token (Recommandé)**
```bash
# 1. Générer un token
# → https://github.com/settings/tokens
# Sélectionnez "repo" scope
# Copiez le token

# 2. Configurer git
git config --global credential.helper store

# 3. Pousser (vous serez invité à entrer le token)
cd ~/AD-Pi400
git push origin main
```

**Option B - Clé SSH**
```bash
# 1. Générer une clé SSH (si nécessaire)
ssh-keygen -t ed25519 -C "tanais.arts@gmail.com"

# 2. Ajouter à GitHub
# → https://github.com/settings/ssh/new
# Copiez le contenu de ~/.ssh/id_ed25519.pub

# 3. Configurer git
git remote set-url origin git@github.com:tanais-arts/AD-Pi.git

# 4. Tester la connexion
ssh -T git@github.com

# 5. Pousser
cd ~/AD-Pi400
git push origin main
```

**Option C - GitHub CLI**
```bash
# 1. Installer GitHub CLI (si nécessaire)
sudo apt-get install gh

# 2. Authentifier
gh auth login

# 3. Pousser
cd ~/AD-Pi400
git push origin main
```

### Vérifier le Push

```bash
cd ~/AD-Pi400
git status
# Devrait afficher: "Votre branche est à jour avec 'origin/main'."
```

---

## 🎬 Phase 3 : Utilisation de l'Application

### Étape 1 : Ajouter des Vidéos

1. Préparez vos fichiers vidéo:
   - Format: MP4 H.264
   - Résolution: 1080p (1920x1080) ou supérieur
   - FPS: 25 ou 30
   - Pas d'accents dans les noms

2. Copiez les fichiers:
```bash
cp mes_videos/*.mp4 ~/AD-Pi400/VIDEOS/
```

### Étape 2 : Créer les Scripts

1. Format CSV (simple):
```csv
Timestamp,Personnage,Genre,Dialogue
00:00:00,Alice,F,"Bienvenue!"
00:00:03,Bob,H,"Enchanté!"
```

2. Ou Excel (.xlsx):
   - Même structure que CSV
   - Plus flexible pour les montages

3. Sauvegardez dans:
```bash
~/AD-Pi400/SCRIPTS/ma_video.csv
# ou
~/AD-Pi400/SCRIPTS/ma_video.xlsx
```

### Étape 3 : Configurer repartition.csv

1. Éditez le fichier:
```bash
nano ~/AD-Pi400/repartition.csv
```

2. Ajoutez vos vidéos (format):
```csv
Fichier video,Nombre de personnages,F,H,categorie,SPEED,Afficher
ma_video_1.mp4,5,3,2,dialogue,1.0,OUI
ma_video_2.mp4,8,4,4,action,1.25,OUI
```

### Étape 4 : Lancer l'Application

**Via le Menu:**
```
Applications → Ateliers Doublage Administration → Double-clic
```

**Via Terminal:**
```bash
cd ~/AD-Pi400
./launch_app.sh
```

### Étape 5 : Synchroniser

1. Ouvrez http://localhost:1348
2. Sélectionnez les vidéos
3. Cliquez sur "Synchroniser"
4. Attendez le traitement
5. Récupérez les résultats dans:
   - Vidéos: `VIDEOS/SYNC/`
   - Métadonnées: `VI/`
   - Logs: `logs/`

---

## 📚 Phase 4 : Optimisation & Maintenance

### Sauvegarde Régulière

```bash
# Sauvegardez la configuration
cp ~/AD-Pi400/repartition.csv ~/backup/repartition.csv.$(date +%Y%m%d)

# Archivez les vidéos traitées
mkdir -p ~/archive
mv ~/AD-Pi400/VIDEOS/SYNC/*.mp4 ~/archive/$(date +%Y%m%d)/
```

### Nettoyage

```bash
# Nettoyez les anciens logs (mensuellement)
rm -f ~/AD-Pi400/logs/*.log.* 

# Nettoyez le cache (si nécessaire)
rm -rf ~/AD-Pi400/outputs/*
rm -rf ~/AD-Pi400/uploads/*
```

### Monitoring

```bash
# Vérifiez l'espace disque
du -sh ~/AD-Pi400/VIDEOS/
du -sh ~/AD-Pi400/VI/

# Vérifiez les logs d'erreur
tail -f ~/AD-Pi400/server.log
```

---

## 🆘 Dépannage

### L'application ne démarre pas

1. Vérifiez les logs:
```bash
cat ~/AD-Pi400/server.log
```

2. Vérifiez que le port 1348 est libre:
```bash
lsof -i :1348
```

3. Relancez le service:
```bash
cd ~/AD-Pi400
./launch_app.sh
```

### Les vidéos ne se synchronisent pas

1. Vérifiez les permissions:
```bash
chmod 755 ~/AD-Pi400/VIDEOS/
chmod 755 ~/AD-Pi400/SCRIPTS/
```

2. Vérifiez le format du script:
```bash
head -1 ~/AD-Pi400/SCRIPTS/ma_video.csv
# Doit avoir: Timestamp,Personnage,Genre,Dialogue
```

3. Vérifiez l'espace disque:
```bash
df -h ~/AD-Pi400/
# Minimum 50% libre requis
```

### Problèmes d'encodage

1. Remplacez les accents:
```bash
rename 's/é/e/g' ~/AD-Pi400/VIDEOS/*
rename 's/à/a/g' ~/AD-Pi400/SCRIPTS/*
```

2. Utilisez des noms ASCII simples

---

## 📞 Ressources

- **Documentation complète:** `PROJECT_STATUS.md`
- **Permissions:** `PERMISSIONS_CHECK.md`
- **Git & GitHub:** `PUSH_TO_GITHUB_INSTRUCTIONS.md`
- **Format scripts:** `SCRIPTS/README.md`
- **Gestion vidéos:** `VIDEOS/README.md`
- **Sorties:** `VI/README.md`

---

## 📊 Checklist Phase 2

- [ ] Authentification GitHub configurée
- [ ] 4 commits poussés avec succès
- [ ] Branche main synchronisée
- [ ] Vérification sur GitHub faite

## 📊 Checklist Phase 3

- [ ] Vidéos ajoutées dans VIDEOS/
- [ ] Scripts créés dans SCRIPTS/
- [ ] repartition.csv configuré
- [ ] Application lancée avec succès
- [ ] Premier sync effectué
- [ ] Résultats vérifiés

## 📊 Checklist Maintenance

- [ ] Sauvegarde repartition.csv faite
- [ ] Espace disque vérifié
- [ ] Logs archivés mensuellement
- [ ] Updates système appliquées

---

**Status:** 🟢 **Prêt à procéder à la Phase 2**
**Date:** 2026-11-13 10:55 CET
**Prochaine action:** Pousser vers GitHub

Bon travail ! 🎬
