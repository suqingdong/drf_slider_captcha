from dataclasses import dataclass, fields
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class CaptchaConfig:
    CACHE_ALIAS: str = "default"
    KEY_PREFIX: str = "slider-captcha:v1"
    WIDTH: int = 320
    HEIGHT: int = 160
    PIECE_WIDTH: int = 60
    CHALLENGE_TTL: int = 120
    TOKEN_TTL: int = 120
    TOLERANCE: float = 4.0
    MIN_DURATION_MS: int = 250
    MAX_DURATION_MS: int = 20000
    MIN_SERVER_ELAPSED_MS: int = 200
    REQUIRE_TRAIL: bool = False
    MAX_TRAIL_POINTS: int = 512
    BIND_IP: bool = False
    PURPOSES: tuple = ("login", "register", "reset_password")
    BACKGROUND_DIR: str | None = None
    CHALLENGE_RATE: str = "30/min"
    VERIFY_RATE: str = "60/min"


def get_config():
    raw = getattr(settings, "SLIDER_CAPTCHA", {})
    if not isinstance(raw, dict):
        raise ImproperlyConfigured("SLIDER_CAPTCHA must be a dictionary.")
    unknown = set(raw) - {f.name for f in fields(CaptchaConfig)}
    if unknown:
        raise ImproperlyConfigured(f"Unknown SLIDER_CAPTCHA options: {sorted(unknown)}")
    config = CaptchaConfig(**raw)
    integers = ("WIDTH", "HEIGHT", "PIECE_WIDTH", "CHALLENGE_TTL", "TOKEN_TTL",
                "MIN_DURATION_MS", "MAX_DURATION_MS", "MIN_SERVER_ELAPSED_MS", "MAX_TRAIL_POINTS")
    for name in integers:
        value = getattr(config, name)
        if type(value) is not int or value < 0:
            raise ImproperlyConfigured(f"SLIDER_CAPTCHA.{name} must be a non-negative integer.")
    if not (32 <= config.PIECE_WIDTH <= 100 and 3 * config.PIECE_WIDTH <= config.WIDTH <= 1024
            and config.PIECE_WIDTH + 16 <= config.HEIGHT <= 512):
        raise ImproperlyConfigured("Invalid CAPTCHA image dimensions.")
    if not (1 <= config.CHALLENGE_TTL <= 3600 and 1 <= config.TOKEN_TTL <= 3600):
        raise ImproperlyConfigured("CAPTCHA TTL must be between 1 and 3600 seconds.")
    if not isinstance(config.TOLERANCE, (int, float)) or isinstance(config.TOLERANCE, bool) or not 0 <= config.TOLERANCE <= 10:
        raise ImproperlyConfigured("TOLERANCE must be a finite number between 0 and 10.")
    if config.MIN_DURATION_MS > config.MAX_DURATION_MS or config.MAX_TRAIL_POINTS < 2:
        raise ImproperlyConfigured("Invalid duration or trajectory limits.")
    if not isinstance(config.PURPOSES, (list, tuple)) or not config.PURPOSES or any(
        not isinstance(p, str) or not p or len(p) > 64 for p in config.PURPOSES
    ):
        raise ImproperlyConfigured("PURPOSES must contain non-empty strings of at most 64 characters.")
    for name in ("BIND_IP", "REQUIRE_TRAIL"):
        if type(getattr(config, name)) is not bool:
            raise ImproperlyConfigured(f"{name} must be a boolean.")
    for name in ("CHALLENGE_RATE", "VERIFY_RATE"):
        value = getattr(config, name)
        if not isinstance(value, str) or not value:
            raise ImproperlyConfigured(f"{name} must be a positive DRF rate string.")
    if not isinstance(config.CACHE_ALIAS, str) or config.CACHE_ALIAS not in settings.CACHES:
        raise ImproperlyConfigured("SLIDER_CAPTCHA.CACHE_ALIAS is not configured in CACHES.")
    if not isinstance(config.KEY_PREFIX, str) or not config.KEY_PREFIX or len(config.KEY_PREFIX) > 80:
        raise ImproperlyConfigured("KEY_PREFIX must be a non-empty string of at most 80 characters.")
    if config.BACKGROUND_DIR is not None and not Path(config.BACKGROUND_DIR).is_dir():
        raise ImproperlyConfigured("BACKGROUND_DIR must be an existing local directory.")
    return config
