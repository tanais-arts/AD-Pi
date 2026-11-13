# 📤 Instructions pour Pusher les Modifications vers GitHub

## Situation Actuelle
✅ **Commit local créé :** `883b246`
```
fix: improve install.sh robustness - handle apt lock and skip interactive prompts
```

❌ **Non encore pushé vers GitHub** (authentification requise)

## 3 Méthodes pour Pousser

### Méthode 1️⃣  : Personal Access Token (PAT) — Recommandée
**Le plus simple et le plus sûr**

1. Générez un token GitHub :
   - Allez sur https://github.com/settings/tokens
   - Cliquez "Generate new token"
   - Sélectionnez scope `repo` (accès dépôts)
   - Copiez le token (⚠️ vous ne pourrez le voir qu'une fois)

2. Configurez git avec le token :
   ```bash
   git config --global credential.helper store
   ```

3. Lors du premier push, entrez vos identifiants :
   ```bash
   cd ~/AD-Pi400
   git push origin main
   ```
   - Username: `tanais-arts` (votre nom d'utilisateur GitHub)
   - Password: `<votre_token_PAT>`

   Git les sauvegarde automatiquement pour les prochains pushes.

### Méthode 2️⃣  : Clé SSH
**Plus sécurisé pour utilisation régulière**

1. Générez une clé SSH (si vous n'en avez pas) :
   ```bash
   ssh-keygen -t ed25519 -C "tanais.arts@gmail.com"
   ```
   Appuyez sur Entrée pour tous les prompts (pas de passphrase).

2. Ajoutez la clé publique à GitHub :
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   - Copiez la sortie
   - Allez sur https://github.com/settings/ssh/new
   - Collez la clé (ne collez QUE la clé publique, pas la privée !)

3. Changez l'URL du dépôt pour SSH :
   ```bash
   cd ~/AD-Pi400
   git remote set-url origin git@github.com:tanais-arts/AD-Pi.git
   ```

4. Testez la connexion SSH :
   ```bash
   ssh -T git@github.com
   # Devrait afficher : Hi tanais-arts! You've successfully authenticated...
   ```

5. Pushez :
   ```bash
   git push origin main
   ```

### Méthode 3️⃣  : CLI GitHub (`gh`)
**Si vous avez déjà GitHub CLI installé**

```bash
gh auth login
# Sélectionnez GitHub.com → HTTPS → Generate a token
# Autorisez pour `repo` scope

cd ~/AD-Pi400
git push origin main
```

## Vérifier que le Push a Réussi

Après le push, vérifiez sur GitHub :
```bash
# Localement, vérifiez que tout est en sync
git status
# Devrait afficher: "Votre branche est à jour avec 'origin/main'."

# Ou accédez directement au dépôt :
# https://github.com/tanais-arts/AD-Pi/commits/main
# Le commit devrait y apparaître
```

## En Cas de Problème

### "Authentication failed"
- Vérifiez que le token/SSH key est valide
- Essayez Méthode 1 avec `credential.helper store`
- Testez votre accès SSH avec `ssh -T git@github.com`

### "Permission denied"
- Vérifiez que vous êtes bien membre du dépôt `tanais-arts/AD-Pi`
- Vérifiez que la clé SSH est bien dans votre compte GitHub

### "Branch protection rules"
- Si vous recevez une erreur de protection de branche, assurez-vous que `main` n'a pas de restrictions

## Commande Rapide (une fois authentifié)

```bash
cd ~/AD-Pi400
git push origin main
```

---
**Commit à pousser :**
```
883b246 - fix: improve install.sh robustness - handle apt lock and skip interactive prompts
```

**Dépôt :** https://github.com/tanais-arts/AD-Pi
**Branche :** main
