# 🌐 Lancer le Serveur Web sur Raspberry Pi 400

Après l'installation via `install.sh`, vous pouvez accéder à l'interface web exactement comme sur macOS.

## ⚡ Démarrage rapide

```bash
cd ~/AD-Pi400
source venv/bin/activate
./run_server.sh
```

Puis ouvrez sur votre ordinateur/téléphone :
```
http://<ip-du-pi>:8080
```

## 📍 Trouver l'adresse IP du Pi

Si vous ne connaissez pas l'IP de votre Pi 400 :

**Option 1 — Sur le Pi :**
```bash
hostname -I
```

**Option 2 — Sur votre ordinateur :**
```bash
# macOS/Linux
arp -n | grep -i raspberry

# Windows (PowerShell)
arp -a | Select-String -Pattern "raspberry"
```

## 🎯 Exemples d'utilisation

### Démarrer sur le port par défaut (8080)
```bash
./run_server.sh
```
Accès : `http://192.168.1.100:8080` (remplacez par votre IP)

### Utiliser un port personnalisé
```bash
./run_server.sh --port 9000
```
Accès : `http://192.168.1.100:9000`

### Afficher l'aide
```bash
./run_server.sh --help
```

## 🔄 Workflow typique

1. **Sur le Pi 400 :**
   ```bash
   cd ~/AD-Pi400
   ./run_server.sh
   ```

2. **Sur votre ordinateur (dans un navigateur) :**
   - Allez à `http://<ip-du-pi>:8080`
   - Cliquez sur **"Upload"**
   - Chargez une vidéo MP4
   - Chargez un script (Excel ou CSV)
   - Cliquez **"Generate"**
   - Regardez la progression en temps réel
   - Téléchargez la vidéo synchronisée

## 📊 Interface disponible

- **Accueil** : Upload vidéo + script, génération
- **Dashboard** : Suivi des vidéos générées
- **Admin** : Configuration des chemins, FPS, etc.
- **Monitoring** : CPU, RAM, débit utilisé
- **Rename** : Renommer les fichiers générés

## 🔧 Configuration du serveur

Après la première installation, un fichier `config.json` est créé. Pour modifier les chemins ou les paramètres :

```bash
nano config.json
```

Paramètres typiques :
```json
{
    "videos_dir": "VIDEOS",
    "scripts_dir": "SCRIPTS",
    "vi_dir": "VI",
    "repartition_csv": "repartition.csv",
    "port": "8080"
}
```

## ⏸️ Arrêter le serveur

Appuyez sur **Ctrl+C** dans le terminal où tourne le serveur.

## 🚀 Lancer en arrière-plan (optionnel)

Si vous voulez que le serveur tourne en permanence :

```bash
cd ~/AD-Pi400
nohup ./run_server.sh > server.log 2>&1 &
```

Pour vérifier que c'est lancé :
```bash
ps aux | grep "python3 server.py"
```

Pour l'arrêter :
```bash
killall python3
```

## 🐛 Dépannage

### Le serveur refuse de se lancer
```
Error: Address already in use
```
→ Quelque chose d'autre utilise le port 8080. Essayez un autre port :
```bash
./run_server.sh --port 9000
```

### Je ne peux pas accéder depuis mon ordinateur
- Vérifiez que le Pi et l'ordinateur sont sur le **même réseau WiFi**
- Vérifiez l'IP du Pi : `hostname -I`
- Testez depuis le Pi lui-même : `curl http://localhost:8080`

### Lenteur ou plantage
- Vérifiez la RAM : `free -h`
- Vérifiez le CPU : `top`
- Si la RAM est faible, arrêtez les autres applications

## 📚 Documentation complète

Voir aussi :
- [INSTALL_ON_PI.md](INSTALL_ON_PI.md) — Guide d'installation
- [RASPBERRY_PI_400.md](RASPBERRY_PI_400.md) — Guide complet avec optimisations
- [QUICK_START.txt](QUICK_START.txt) — Démarrage ultra-rapide
