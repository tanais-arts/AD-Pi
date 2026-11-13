#!/bin/bash
################################################################################
# AD Raspberry Pi 400 Installer — Version ARM64 dédiée
#
# Usage:
#   ./install.sh
#
# Installation complète et automatisée pour Raspberry Pi 400 :
#   • Dépendances système (FFmpeg, Python)
#   • Environnement virtuel Python
#   • Packages Python (numpy, pandas, moviepy, etc)
#   • Structure de répertoires
#   • Tests de vérification
#
# Testé sur : Raspberry Pi OS 64-bit (Debian Bookworm/Bullseye)
#
################################################################################

set -e  # Exit on error

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Couleurs pour l'output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Chemins
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/AD-Pi400"
VENV_DIR="$INSTALL_DIR/venv"
LOG_FILE="$INSTALL_DIR/install.log"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FONCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log() {
    echo -e "${BLUE}[AD]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${CYAN}[i]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  Les Ateliers Doublage — Raspberry Pi 400 Installation    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

section() {
    echo ""
    log "════════════════════════════════════════════════════════════════"
    log "$1"
    log "════════════════════════════════════════════════════════════════"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN SCRIPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

clear
header

# Créer le dossier d'installation d'abord (pour les logs)
mkdir -p "$INSTALL_DIR"
echo "Installation commencée : $(date)" > "$LOG_FILE"

section "VÉRIFICATION DE L'ENVIRONNEMENT"

# Vérifier Pi 400
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
    log_success "Détecté : $PI_MODEL"
else
    log_warning "Impossible de vérifier le modèle Pi (peut être en VM)"
fi

# Vérifier architecture
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    log_success "Architecture ARM64 détectée ($ARCH)"
else
    log_warning "Architecture non-ARM64 détectée ($ARCH) — certains packages peuvent ne pas compiler"
fi

# Vérifier Python3
if ! command -v python3 &> /dev/null; then
    log_error "Python3 n'est pas installé"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log_success "Python3 $PYTHON_VERSION trouvé"

# Vérifier sudo
log_info "Vérification des permissions sudo..."
if ! sudo -n true 2>/dev/null; then
    log_warning "Vous aurez besoin d'entrer votre mot de passe sudo"
fi

echo ""
log "Installation dans : $INSTALL_DIR"
log "Scripts depuis : $SCRIPT_DIR"
echo ""

# Demander confirmation
echo -e "${BLUE}Continuer l'installation ? (y/n)${NC}"
read -n 1 -r REPLY
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_error "Installation annulée."
    exit 0
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 1 : Dépendances système
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 1 : Dépendances système"

log "Mise à jour des paquets (peut prendre 1-2 min)..."
sudo apt-get update -qq >> "$LOG_FILE" 2>&1 || log_warning "apt update échoué (ignoré)"

# Liste des dépendances
DEPS=(
    "ffmpeg"
    "python3-pip"
    "python3-venv"
    "python3-dev"
    "build-essential"
    "libatlas-base-dev"
    "libopenblas-dev"
    "gfortran"
    "liblapack-dev"
    "libharfbuzz0b"
    "libwebp6"
    "libtiff5"
    "libjasper1"
    "libssl-dev"
    "libffi-dev"
    "zlib1g-dev"
)

log "Installation des dépendances (${#DEPS[@]} paquets)..."
for dep in "${DEPS[@]}"; do
    if dpkg -l | grep -q "^ii  $dep"; then
        log_success "$dep (déjà installé)"
    else
        log "  → $dep..."
        sudo apt-get install -y -qq "$dep" >> "$LOG_FILE" 2>&1 || log_warning "$dep : échec (non-critique)"
    fi
done

log_success "Dépendances système OK"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 2 : Structure de répertoires
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 2 : Structure de répertoires"

# Vérifier si installation existe
if [ -d "$INSTALL_DIR" ] && [ "$(ls -A $INSTALL_DIR 2>/dev/null)" ]; then
    log_warning "Le répertoire $INSTALL_DIR n'est pas vide"
    read -p "$(echo -e ${YELLOW}Écraser l\'installation existante ? (y/n)${NC} )" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Sauvegarde de l'ancienne installation..."
        BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%s)"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
        log_warning "Sauvegardé dans : $BACKUP_DIR"
        mkdir -p "$INSTALL_DIR"
    fi
else
    mkdir -p "$INSTALL_DIR"
    log_success "Répertoire créé : $INSTALL_DIR"
fi

# Créer les sous-répertoires
for dir in VIDEOS SCRIPTS VI GENERATED VIDEOS/SYNC logs; do
    mkdir -p "$INSTALL_DIR/$dir"
    log_success "📁 $INSTALL_DIR/$dir"
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 3 : Copie du programme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 3 : Copie du programme"

log "Copie des fichiers Python..."

# Copier depuis le même répertoire que le script
cp -v "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1
cp -v "$SCRIPT_DIR"/requirements.txt "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1
cp -v "$SCRIPT_DIR"/FPS.txt "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1

# Copier docs si présentes
[ -f "$SCRIPT_DIR/RASPBERRY_PI_400.md" ] && cp "$SCRIPT_DIR/RASPBERRY_PI_400.md" "$INSTALL_DIR/"
[ -f "$SCRIPT_DIR/CERTBOT.md" ] && cp "$SCRIPT_DIR/CERTBOT.md" "$INSTALL_DIR/"

# Vérifier fichiers critiques
log_info "Vérification des fichiers essentiels..."
CRITICAL_FILES=("server.py" "generate_sync.py" "batch_sync.py" "requirements.txt")
for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$INSTALL_DIR/$file" ]; then
        log_success "$file ✓"
    else
        log_error "$file manquant !"
        exit 1
    fi
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 4 : Environnement virtuel Python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 4 : Environnement virtuel Python"

if [ -d "$VENV_DIR" ]; then
    log_warning "venv existe déjà, utilisation..."
else
    log "Création de l'environnement virtuel (1-2 min)..."
    python3 -m venv "$VENV_DIR" >> "$LOG_FILE" 2>&1
    log_success "venv créé"
fi

log "Activation du venv..."
source "$VENV_DIR/bin/activate" >> "$LOG_FILE" 2>&1

log "Mise à jour de pip, setuptools, wheel..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel --quiet >> "$LOG_FILE" 2>&1
log_success "pip à jour"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 5 : Packages Python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 5 : Packages Python (peut prendre 30-60 min)"

log_info "⏳ Compilation ARM64 en cours... numpy et pandas sont LENTS (c'est normal !)"
log_info "   Patientez, laissez la compilation se faire. Aller boire un café ☕"
echo ""

if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    log "Installation des dépendances Python..."
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_success "Packages Python installés ✓"
    else
        log_error "Erreur lors de l'installation des packages"
        log_warning "Vérifier le fichier log : $LOG_FILE"
        exit 1
    fi
else
    log_error "requirements.txt non trouvé !"
    exit 1
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 6 : Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 6 : Configuration"

# Créer config.json
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    log "Création de config.json..."
    
    CURRENT_USER=$(whoami)
    cat > "$INSTALL_DIR/config.json" << EOF
{
  "videos_dir": "$INSTALL_DIR/VIDEOS",
  "scripts_dir": "$INSTALL_DIR/SCRIPTS",
  "vi_dir": "$INSTALL_DIR/VI",
  "repartition_csv": "$INSTALL_DIR/repartition.csv",
  "port": "1348"
}
EOF
    
    log_success "config.json créé pour l'utilisateur: $CURRENT_USER"
else
    log_warning "config.json existe déjà"
fi

# Créer repartition.csv
if [ ! -f "$INSTALL_DIR/repartition.csv" ]; then
    log "Création de repartition.csv..."
    echo "Fichier vidéo,Nombre de personnages,F,H,catégorie,SPEED,Afficher" > "$INSTALL_DIR/repartition.csv"
    log_success "repartition.csv créé"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 7 : Scripts de lancement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 7 : Scripts de lancement"

# Script de lancement rapide
cat > "$INSTALL_DIR/sync.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
exec python3 "$@"
EOF
chmod +x "$INSTALL_DIR/sync.sh"
log_success "Créé : $INSTALL_DIR/sync.sh"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ÉTAPE 8 : Tests et vérification
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "ÉTAPE 8 : Tests et vérification"

log "Vérification des imports Python..."
"$VENV_DIR/bin/python3" << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
import sys
print(f"✓ Python {sys.version.split()[0]}")
deps = ['numpy', 'pandas', 'PIL', 'imageio_ffmpeg', 'flask', 'moviepy']
for dep in deps:
    try:
        __import__(dep)
        print(f"✓ {dep}")
    except ImportError:
        print(f"✗ {dep} (ERREUR)")
PYEOF

# Vérifier FFmpeg
log_info "Vérification de FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3)
    log_success "FFmpeg OK ($FFMPEG_VERSION)"
else
    log_error "FFmpeg non trouvé !"
    exit 1
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RÉSUMÉ FINAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
section "✅ INSTALLATION TERMINÉE"

cat << EOF
╔════════════════════════════════════════════════════════════╗
║                     PRÊT À UTILISER                        ║
╚════════════════════════════════════════════════════════════╝

📁 Répertoire installation : $INSTALL_DIR
📄 Fichiers de log : $LOG_FILE
🐍 Python venv : $VENV_DIR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 DÉMARRAGE RAPIDE :

OPTION 1️⃣  — Application bureau (RECOMMANDÉ) :
   cd $INSTALL_DIR
   cp Ateliers-Doublage.desktop ~/.local/share/applications/
   mkdir -p ~/.local/share/icons
   cp Icone.png ~/.local/share/icons/
   update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
   
   → Double-cliquez sur "Ateliers Doublage Administration" dans le menu
   → L'interface web s'ouvre automatiquement sur le port 1348

OPTION 2️⃣  — Interface web (port 8080) :
   cd $INSTALL_DIR
   ./run_server.sh
   → Accédez à http://localhost:8080

OPTION 3️⃣  — Ligne de commande (CLI) :
   cd $INSTALL_DIR
   source venv/bin/activate
   python3 generate_sync.py VIDEOS/video.mp4 SCRIPTS/script.xlsx
   
   Résultat : $INSTALL_DIR/VIDEOS/SYNC/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 Documentation :
   • $INSTALL_DIR/README.md
   • $INSTALL_DIR/RASPBERRY_PI_400.md
   • $INSTALL_DIR/DESKTOP_APP.md (guide application bureau)
   • $INSTALL_DIR/RUN_SERVER.md (guide serveur web)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💾 Espace disque utilisé :
EOF

du -sh "$INSTALL_DIR" 2>/dev/null || echo "   (à calculer)"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CRÉATION AUTOMATIQUE DU RACCOURCI DESKTOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log_info "Création du raccourci application bureau..."

# Créer les répertoires nécessaires
APPLICATIONS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons"

mkdir -p "$APPLICATIONS_DIR" 2>/dev/null || true
mkdir -p "$ICONS_DIR" 2>/dev/null || true

# Copier le fichier .desktop
if [ -f "$INSTALL_DIR/Ateliers-Doublage.desktop" ]; then
    cp "$INSTALL_DIR/Ateliers-Doublage.desktop" "$APPLICATIONS_DIR/" 2>/dev/null && \
    log_success "✓ Raccourci copié dans le menu" || \
    log_warning "⚠️  Impossible de copier le raccourci"
else
    log_warning "⚠️  Fichier Ateliers-Doublage.desktop non trouvé"
fi

# Copier l'icône
if [ -f "$INSTALL_DIR/Icone.png" ]; then
    cp "$INSTALL_DIR/Icone.png" "$ICONS_DIR/" 2>/dev/null && \
    log_success "✓ Icône copiée" || \
    log_warning "⚠️  Impossible de copier l'icône"
else
    log_warning "⚠️  Fichier Icone.png non trouvé"
fi

# Mettre à jour la base de données desktop
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null && \
    log_success "✓ Base de données mise à jour" || \
    log_warning "⚠️  Impossible de mettre à jour la base de données"
fi

# Créer optionnellement un lien sur le desktop (si disponible)
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    if [ -f "$APPLICATIONS_DIR/Ateliers-Doublage.desktop" ]; then
        # Créer un lien symbolique au lieu de copier
        ln -sf "$APPLICATIONS_DIR/Ateliers-Doublage.desktop" "$DESKTOP_DIR/" 2>/dev/null || \
        cp "$APPLICATIONS_DIR/Ateliers-Doublage.desktop" "$DESKTOP_DIR/" 2>/dev/null && \
        log_success "✓ Raccourci aussi sur le bureau" || \
        log_info "ℹ️  Raccourci dans le menu (Desktop non accessible)"
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
section "✅ RACCOURCI CRÉÉ"

cat << EOF

🖱️  Cherchez "Ateliers Doublage Administration" dans le menu des applications
    ou sur votre bureau, puis double-cliquez.

📍 Localisation du raccourci :
   • Menu/Applications : $APPLICATIONS_DIR/Ateliers-Doublage.desktop
   • Bureau (optionnel) : $DESKTOP_DIR/Ateliers-Doublage.desktop

⚡ Premier démarrage :
   1. Double-cliquez sur le raccourci
   2. Le serveur démarre automatiquement (port 1348)
   3. Le navigateur s'ouvre à http://localhost:1348
   4. Utilisez l'interface comme sur macOS

🎬 Interface prête !

EOF

log_success "Installation complète ! Enjoy 🎬"
