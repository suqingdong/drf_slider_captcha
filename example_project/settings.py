"""Development example only. Integrate the reusable app into your real project."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-slider-captcha-do-not-use-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "rest_framework", "drf_slider_captcha"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "example_project.urls"
WSGI_APPLICATION = "example_project.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
USE_TZ = True
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "slider-captcha-demo"}}
if os.getenv("REDIS_URL"):
    CACHES["default"] = {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["REDIS_URL"]}
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"]}
SLIDER_CAPTCHA = {"CHALLENGE_TTL": 120, "TOKEN_TTL": 120, "TOLERANCE": 4}
if os.getenv("CAPTCHA_BACKGROUND_DIR"):
    SLIDER_CAPTCHA["BACKGROUND_DIR"] = os.environ["CAPTCHA_BACKGROUND_DIR"]
else:
    SLIDER_CAPTCHA["BACKGROUND_DIR"] = str(BASE_DIR / "captcha_backgrounds")