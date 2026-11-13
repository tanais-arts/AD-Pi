#!/bin/bash
# launch_app.sh — Lanceur d'application Linux pour "Ateliers Doublage Administration"
# 
# Cette application :
# 1. Lance le serveur Ateliers Doublage sur le port 1348
# 2. Ouvre automatiquement l'interface web dans le navigateur
# 3. Gère l'arrêt propre du serveur
#
# Usage: ./launch_app.sh [--help]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT=1348
PIDFILE="$SCRIPT_DIR/.server.pid"
LOGFILE="$SCRIPT_DIR/server.log"
VENV_DIR="$SCRIPT_DIR/venv"

# Fonction pour afficher l'aide
show_help() {
    cat << EOF
╔════════════════════════════════════════════════════════════╗
║          Ateliers Doublage — Application Linux             ║
╚════════════════════════════════════════════════════════════╝

Cette application lance le serveur "Ateliers Doublage" 
et ouvre l'interface web.

Usage:
  $0                    Lancer l'application
  $0 --help             Afficher cette aide

Ports :
  Serveur web  : http://localhost:$PORT
  
Arrêt :
  Cliquez sur le bouton de fermeture ou Ctrl+C dans le terminal

Logs :
  $LOGFILE

EOF
}

# Vérifier les arguments
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_help
    exit 0
fi

# Vérifier que le venv existe
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ ERREUR : L'environnement Python n'a pas été trouvé${NC}"
    echo ""
    echo "Veuillez d'abord exécuter l'installation :"
    echo "  chmod +x install.sh"
    echo "  ./install.sh"
    exit 1
fi

# Fonction pour arrêter proprement le serveur
cleanup() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${YELLOW}⏸️  Arrêt du serveur (PID $PID)...${NC}"
            kill "$PID"
            sleep 2
        fi
        rm -f "$PIDFILE"
    fi
    echo -e "${BLUE}👋 Au revoir !${NC}"
}

# Trap pour arrêt propre
trap cleanup EXIT INT TERM

# Vérifier si un serveur tourne déjà
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Un serveur tourne déjà (PID $OLD_PID)${NC}"
        echo "Arrêt du serveur précédent..."
        kill "$OLD_PID"
        sleep 1
    fi
fi

# Obtenir l'IP locale
LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
fi

# Afficher l'en-tête
clear
cat << EOF
╔════════════════════════════════════════════════════════════╗
║          Ateliers Doublage — Administration                ║
╚════════════════════════════════════════════════════════════╝

📊 Démarrage du serveur...
🖥️  Port : $PORT
🌐 URL : http://localhost:$PORT
📡 Réseau : http://$LOCAL_IP:$PORT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

# Activer le venv
source "$VENV_DIR/bin/activate"

# Démarrer le serveur en arrière-plan
echo "🚀 Lancement du serveur Flask..."
nohup python3 server.py --port "$PORT" --host 0.0.0.0 > "$LOGFILE" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PIDFILE"

# Attendre que le serveur démarre
echo "⏳ Attente du serveur (patience 5 secondes)..."
sleep 5

# Vérifier que le serveur a bien démarré
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}❌ Le serveur n'a pas pu démarrer${NC}"
    echo ""
    echo "Vérifiez les logs :"
    cat "$LOGFILE"
    exit 1
fi

echo -e "${GREEN}✅ Serveur lancé (PID $SERVER_PID)${NC}"
echo ""

# Ouvrir le navigateur
echo "🌐 Ouverture du navigateur..."

# Essayer différents navigateurs
BROWSER_OPENED=0

# Essayer avec xdg-open (standard Linux)
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:$PORT" 2>/dev/null &
    BROWSER_OPENED=1
fi

# Fallback : Chromium
if [ $BROWSER_OPENED -eq 0 ] && command -v chromium-browser &> /dev/null; then
    chromium-browser "http://localhost:$PORT" 2>/dev/null &
    BROWSER_OPENED=1
fi

# Fallback : Chrome
if [ $BROWSER_OPENED -eq 0 ] && command -v google-chrome &> /dev/null; then
    google-chrome "http://localhost:$PORT" 2>/dev/null &
    BROWSER_OPENED=1
fi

# Fallback : Firefox
if [ $BROWSER_OPENED -eq 0 ] && command -v firefox &> /dev/null; then
    firefox "http://localhost:$PORT" 2>/dev/null &
    BROWSER_OPENED=1
fi

if [ $BROWSER_OPENED -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Impossible d'ouvrir automatiquement le navigateur${NC}"
    echo "Ouvrez manuellement : http://localhost:$PORT"
else
    echo -e "${GREEN}✅ Navigateur ouvert${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Interface disponible : http://localhost:$PORT"
echo ""
echo "⚙️  Pour arrêter : Fermerez le navigateur ou Ctrl+C ici"
echo ""
echo "📄 Logs : $LOGFILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Garder le processus lanceur actif
wait $SERVER_PID
