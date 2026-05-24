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

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}

if EMAIL_BACKEND.endswith("console.EmailBackend"):  # noqa: F405
    import warnings
    warnings.warn(
        "EMAIL_BACKEND is set to console in production; outbound quote emails will not be delivered. "
        "Set EMAIL_BACKEND to an SMTP backend in your environment.",
        RuntimeWarning,
        stacklevel=2,
    )
