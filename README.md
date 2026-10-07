# Recos Cardio

Application web personnelle (iPhone, hors ligne) de lecture, de révision et d’entraînement sur les recommandations européennes de cardiologie.

Le contenu (`data/content.json`) est chiffré (AES-256-GCM, clé dérivée du mot de passe par PBKDF2-SHA256, 600 000 itérations). Les sources rédigées ne sont pas publiées. Usage strictement personnel ; ce dépôt ne reproduit aucun texte de la Société européenne de cardiologie en clair.

- `tools/build.py` : transforme les sources rédigées en `build/contenu.json`.
- `tools/crypt.py` : chiffre ce fichier vers `data/content.json` (mot de passe dans `RC_PASSWORD`).
