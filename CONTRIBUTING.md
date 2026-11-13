# Contrat de contribution

Merci de contribuer à **AD-Pi400** !

## Code de conduite

- Respectueux et constructif
- Pas de spam ou contenu offensant
- Support mutuel entre contributeurs

## Avant de contribuer

1. **Fork** le repo
2. **Branche** : `git checkout -b feature/ma-feature`
3. **Commit** : `git commit -m "Description claire"`
4. **Push** : `git push origin feature/ma-feature`
5. **Pull Request** : Ouvrir une PR vers `main`

## Guidelines

### Code

- Python 3.9+
- Suivre les styles existants
- Commenter les sections complexes
- Pas de dépendances inutiles (maintient ARM Pi léger)

### Documentation

- README clair pour chaque feature
- Docstrings en français dans le code
- Exemples d'utilisation

### Commits

```
feat: Ajouter support XYZ
fix: Corriger bug dans generate_sync.py
docs: Améliorer documentation installation
chore: Mettre à jour requirements.txt
```

### Tests

- Tester sur **Raspberry Pi 400** si possible
- Vérifier que `install.sh` passe sans erreur
- Tester avec FPS différentes (25, 30, 50)

## Branches

- `main` : Version stable (protection)
- `develop` : Développement (en cours)
- `feature/*` : Nouvelles features
- `bugfix/*` : Corrections bugs
- `hotfix/*` : Urgences en production

## Signalement de bugs

1. Vérifier que le bug existe dans la dernière version
2. Ouvrir une issue avec :
   - Description claire
   - Étapes à reproduire
   - Environnement (Pi 400, Pi OS version)
   - Logs/erreurs

## Demandes de features

1. Vérifier que la feature n'existe pas
2. Proposer dans une issue
3. Discuter de la pertinence
4. Développer et PR

## License

Le code est sous la même license que le projet principal AD.

## Questions ?

Créer une issue ou contacter l'équipe.

---

**Merci de votre contribution ! 🙏**
