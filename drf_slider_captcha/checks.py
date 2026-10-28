from django.conf import settings
from django.core.checks import Error, Warning, register
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import SimpleRateThrottle

from .conf import get_config


@register()
def check_captcha_settings(app_configs, **kwargs):
    try:
        config = get_config()
        for rate in (config.CHALLENGE_RATE, config.VERIFY_RATE):
            count, period = SimpleRateThrottle.parse_rate(None, rate)
            if count is None or count < 1 or period < 1:
                raise ValueError("rate must be positive")
    except (ImproperlyConfigured, ValueError, TypeError, KeyError) as error:
        return [Error(str(error), id="slider_captcha.E001")]
    backend = settings.CACHES[config.CACHE_ALIAS]["BACKEND"]
    supported = ("django.core.cache.backends.locmem.LocMemCache",
                 "django.core.cache.backends.redis.RedisCache",
                 "django.core.cache.backends.memcached.PyMemcacheCache",
                 "django.core.cache.backends.memcached.PyLibMCCache",
                 "django_redis.cache.RedisCache")
    if backend not in supported:
        return [Error("Use an atomic-add cache backend: Redis, Memcached or development-only LocMem.",
                      id="slider_captcha.E002")]
    if backend.endswith("LocMemCache") and not settings.DEBUG:
        return [Warning("LocMemCache is process-local. Use a shared Redis/Memcached cache in production.",
                        id="slider_captcha.W001")]
    return []
