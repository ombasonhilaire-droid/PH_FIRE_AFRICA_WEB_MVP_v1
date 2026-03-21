# PH FIRE AFRICA — Web MVP (prêt à tester)

✅ Fonctionne en local sur Mac / Windows / Linux.

## Fonctionnalités (MVP)
- Inscription / connexion (email ou téléphone)
- Fil d’actualité (posts texte + image)
- Likes + commentaires
- Abonnements (follow/unfollow)
- Messagerie privée
- Notifications (follow/like/comment)
- Profil + édition (nom/bio)
- API JSON simple: `/api/posts`, `/api/me`

## Lancer l’app (Mac / Linux)
```bash
cd ph_fire_africa_web_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Ouvre: http://127.0.0.1:5000

## Lancer l’app (Windows PowerShell)
```powershell
cd ph_fire_africa_web_mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app run
```

## Comptes démo
- demo1 / demo2
- mot de passe: demo123

Si tu veux reinitialiser la base:
```bash
flask --app app init-db
flask --app app seed-demo
```

## Notes
- DB SQLite dans `instance/ph_fire_africa.db`
- Uploads dans `static/uploads/`
