# Business Quote Generator

A Django 5 quote workflow app for small service businesses. It supports client and catalog management, per-user quotes, HTMX line-item editing, public quote links, accept/decline tracking, email sending, and on-demand PDF export.

## Stack

- Python 3.12
- Django 5
- Django templates, HTMX, Tailwind CSS
- SQLite for development
- PostgreSQL on Railway
- Pillow for logos
- ReportLab for PDFs
- WhiteNoise for production static files

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata quotes/fixtures/seed.json
python manage.py runserver
```

The seed account is `demo` with password `demo12345`.

## Environment

Set these in `.env` locally and Railway in production:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `EMAIL_BACKEND`
- `DEFAULT_FROM_EMAIL`
- `CSRF_TRUSTED_ORIGINS`

## Public Quote Flow

A draft quote gets a public token the first time it is sent. The public URL is `/q/<token>/`. The first public hit transitions `Sent` to `Viewed`, and the accept/decline buttons write an `ActivityEvent` with IP address and user agent metadata.

## Commands

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

## Deployment

Railway should use `config.settings.prod`, provide `DATABASE_URL`, and run the `railway.toml` start command. Static files are served with WhiteNoise after `collectstatic`.
