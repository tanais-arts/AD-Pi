# Instructions pour pousser vers GitHub

## Prérequis

1. **Authentification GitHub** (token ou clé SSH)
2. **Git configuré** localement

## Configuration GitHub CLI (recommandé)

### Installation

```bash
# Sur macOS
brew install gh

# Ou via Debian/Ubuntu
sudo apt install gh
```

### Authentification

```bash
gh auth login
# Choisir : GitHub.com
# Choisir : HTTPS ou SSH
# Suivre les instructions
```

## Push vers GitHub

### Méthode 1 : GitHub CLI (plus facile)

```bash
cd /Users/tanaismusic/Documents/AD-Pi400

# Vérifier l'authentification
gh auth status

# Pousser la branche main
git push -u origin main
```

### Méthode 2 : Git classique (HTTPS)

```bash
cd /Users/tanaismusic/Documents/AD-Pi400

# Pousser
git push -u origin main

# Si demandé, entrer le token GitHub (voir GitHub Settings > Developer Settings)
```

### Méthode 3 : Git avec SSH

```bash
# Configurer SSH si nécessaire
# Voir : https://docs.github.com/en/authentication/connecting-to-github-with-ssh

cd /Users/tanaismusic/Documents/AD-Pi400

# Vérifier le remote
git remote -v
# Devrait montrer : git@github.com:tanais-arts/AD-Pi.git

# Pousser
git push -u origin main
```

## Vérification

```bash
# Voir la branche locale
git branch -vv

# Voir l'historique
git log --oneline

# Vérifier le remote
git remote -v
```

## Après le push

1. Aller sur https://github.com/tanais-arts/AD-Pi
2. Vérifier que les fichiers sont présents
3. Vérifier que le commit est visible dans l'historique

## Futur : Récupérer sur Pi 400

```bash
# Sur le Raspberry Pi 400
ssh pi@raspberrypi.local
cd ~
git clone https://github.com/tanais-arts/AD-Pi.git AD-Pi400
cd AD-Pi400
./install.sh
```

## Aide

- GitHub Docs : https://docs.github.com/
- Git Docs : https://git-scm.com/doc
