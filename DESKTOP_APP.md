# 🚀 Installation de l'application "Ateliers Doublage" sur Raspberry Pi 400

Après l'installation d'AD-Pi400, vous pouvez créer un **raccourci d'application Linux** (`.desktop`) qui s'affiche sur le bureau ou le menu.

## ⚡ Installation automatique du raccourci

```bash
cd ~/AD-Pi400

# Copier le raccourci dans le menu d'applications
cp Ateliers-Doublage.desktop ~/.local/share/applications/

# Copier l'icône
mkdir -p ~/.local/share/icons
cp Icone.png ~/.local/share/icons/Icone.png

# Mettre à jour la base de données des applications
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

## 🖥️ Afficher sur le bureau

Si vous voulez que l'icône s'affiche sur le **bureau** (au lieu que dans le menu) :

```bash
# Créer un lien symbolique sur le bureau
ln -s ~/AD-Pi400/Ateliers-Doublage.desktop ~/Desktop/
```

Ou copier directement :
```bash
cp ~/AD-Pi400/Ateliers-Doublage.desktop ~/Desktop/
chmod +x ~/Desktop/Ateliers-Doublage.desktop
```

## ✅ Utilisation

### Double-clic sur l'icône

1. **Trouvez l'icône** :
   - **Sur le bureau** : recherchez "Ateliers Doublage"
   - **Dans le menu** : Applications → Multimedia → "Ateliers Doublage Administration"

2. **Double-cliquez** : L'application :
   - Lance le serveur sur le port **1348**
   - Ouvre automatiquement le navigateur
   - Affiche l'interface web

3. **Utilisez normalement** :
   - Upload vidéo + script
   - Cliquez "Generate"
   - Téléchargez le résultat

4. **Fermer** :
   - Fermez le navigateur ou appuyez Ctrl+C dans le terminal

## 🔧 Configuration manuelle

Si l'installation automatique ne fonctionne pas, vous pouvez :

### Option 1 : Lancer depuis le terminal

```bash
cd ~/AD-Pi400
./launch_app.sh
```

### Option 2 : Créer le raccourci manuellement

```bash
# Éditer le fichier de configuration
nano ~/.local/share/applications/Ateliers-Doublage.desktop
```

Assurez-vous que le contenu ressemble à :
```
[Desktop Entry]
Version=1.0
Type=Application
Name=Ateliers Doublage Administration
Comment=Gestion des vidéos synchronisées
Icon=/home/pi/AD-Pi400/Icone
Exec=bash -c 'cd /home/pi/AD-Pi400 && ./launch_app.sh'
Terminal=true
Categories=AudioVideo;Utility;
```

(Remplacez `/home/pi/AD-Pi400` par le chemin réel de votre installation)

## 📊 Ce que l'application fait

| Étape | Détail |
|-------|--------|
| 1. Double-clic | Lance `launch_app.sh` |
| 2. Vérifie venv | S'assure que Python est bien configuré |
| 3. Lance serveur | `python3 server.py --port 1348` |
| 4. Ouvre navigateur | `http://localhost:1348` |
| 5. Attend votre utilisation | Interface web complète |
| 6. Arrêt propre | Quand vous fermez : le serveur s'arrête |

## 🔗 Port utilisé

- **Port 1348** : Port standard "Ateliers Doublage"
- **Accès local** : `http://localhost:1348`
- **Accès réseau** : `http://<ip-du-pi>:1348`

## 🐛 Troubleshooting

### Le raccourci ne s'affiche pas
```bash
# Recréer le répertoire d'applications
mkdir -p ~/.local/share/applications/
cp ~/AD-Pi400/Ateliers-Doublage.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

### Le double-clic ne fait rien
```bash
# Vérifier que le fichier est exécutable
chmod +x ~/AD-Pi400/launch_app.sh
ls -la ~/AD-Pi400/launch_app.sh
# Doit afficher : -rwxr-xr-x ... launch_app.sh
```

### Le serveur ne démarre pas
```bash
# Vérifier les logs
cat ~/AD-Pi400/server.log
```

### L'icône ne s'affiche pas
```bash
# Vérifier que l'icône est bien placée
ls -l ~/.local/share/icons/Icone.png
# Sinon la copier :
cp ~/AD-Pi400/Icone.png ~/.local/share/icons/
```

## 📚 Autres options

- **Lancer depuis terminal** : `~/AD-Pi400/launch_app.sh`
- **Interface web seule** : `~/AD-Pi400/run_server.sh`
- **CLI (ligne de commande)** : `python3 generate_sync.py ...`

## 🎬 Exemple complet

```bash
# 1. Installation
cd ~/AD-Pi400
./install.sh  # 45-60 min

# 2. Créer le raccourci
cp Ateliers-Doublage.desktop ~/.local/share/applications/
mkdir -p ~/.local/share/icons
cp Icone.png ~/.local/share/icons/

# 3. Mettre à jour le menu
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

# 4. Afficher sur le bureau
ln -s ~/AD-Pi400/Ateliers-Doublage.desktop ~/Desktop/

# 5. Double-clic sur le desktop !
```

Vous êtes prêt ! 🎬
