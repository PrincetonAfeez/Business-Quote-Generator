import importlib.util
import os
from urllib.parse import urlparse

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

if importlib.util.find_spec("whitenoise"):
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

database_url = os.getenv("DATABASE_URL")
if database_url:
    parsed = urlparse(database_url)
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or "",
            "OPTIONS": {"sslmode": "require"},
        }
    }
