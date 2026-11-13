#!/bin/bash
################################################################################
# AD Raspberry Pi 400 — Désinstallation propre
#
# Usage:
#   ./uninstall.sh
#
# Supprime :
#   • L'environnement virtuel Python
#   • Les fichiers temporaires
#   • Les configurations locales
#
# CONSERVE :
#   • Répertoires VIDEOS, SCRIPTS, VI
#   • Le fichier repartition.csv
#   • Les logs d'installation
#
################################################################################

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/AD-Pi400"

echo -e "${RED}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Désinstallation — Les Ateliers Doublage              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Vérifier que le répertoire existe
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}[!]${NC} Aucune installation trouvée dans $INSTALL_DIR"
    exit 0
fi

echo -e "${YELLOW}[!]${NC} AVERTISSEMENT :"
echo "    • L'environnement virtuel Python sera SUPPRIMÉ"
echo "    • Les fichiers de code seront SUPPRIMÉS"
echo "    • Les répertoires VIDEOS, SCRIPTS, VI seront CONSERVÉS"
echo "    • Le fichier repartition.csv sera CONSERVÉ"
echo ""

read -p "$(echo -e ${RED}Êtes-vous certain ? (y/n)${NC} )" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}[AD]${NC} Désinstallation annulée."
    exit 0
fi

echo ""
echo -e "${BLUE}[AD]${NC} Désinstallation en cours..."

# Supprimer le venv
if [ -d "$INSTALL_DIR/venv" ]; then
    echo -e "${BLUE}[AD]${NC} Suppression de l'environnement virtuel..."
    rm -rf "$INSTALL_DIR/venv"
    echo -e "${GREEN}[✓]${NC} venv supprimé"
fi

# Supprimer les fichiers Python
echo -e "${BLUE}[AD]${NC} Suppression des fichiers de code..."
for file in server.py generate_sync.py batch_sync.py debug_match.py normalize_scripts.py syllable_count.py; do
    if [ -f "$INSTALL_DIR/$file" ]; then
        rm "$INSTALL_DIR/$file"
        echo -e "${GREEN}[✓]${NC} $file supprimé"
    fi
done

# Supprimer les fichiers temporaires
echo -e "${BLUE}[AD]${NC} Nettoyage des fichiers temporaires..."
rm -rf "$INSTALL_DIR/__pycache__" 2>/dev/null || true
rm -rf "$INSTALL_DIR/*.pyc" 2>/dev/null || true
rm -rf "$INSTALL_DIR/outputs" 2>/dev/null || true
rm -rf "$INSTALL_DIR/uploads" 2>/dev/null || true
rm -rf "$INSTALL_DIR/sessions" 2>/dev/null || true
echo -e "${GREEN}[✓]${NC} Fichiers temporaires supprimés"

# Garder VIDEOS, SCRIPTS, VI, repartition.csv
echo ""
echo -e "${GREEN}[✓]${NC} CONSERVÉS (données utilisateur) :"
echo "    • $INSTALL_DIR/VIDEOS"
echo "    • $INSTALL_DIR/SCRIPTS"
echo "    • $INSTALL_DIR/VI"
echo "    • $INSTALL_DIR/repartition.csv"

echo ""
echo -e "${GREEN}[✓]${NC} Désinstallation complète"
echo ""
echo -e "${YELLOW}[!]${NC} Pour réinstaller :"
echo "    cd $INSTALL_DIR"
echo "    chmod +x install.sh"
echo "    ./install.sh"
echo ""
