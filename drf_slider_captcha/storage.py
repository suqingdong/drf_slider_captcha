import hashlib
import math
import time

from django.core.cache import caches

from .exceptions import CaptchaError


def key_for(config, namespace, identifier):
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{config.KEY_PREFIX}:{namespace}:{digest}"


def store(config, namespace, identifier, state, ttl):
    try:
        result = caches[config.CACHE_ALIAS].set(key_for(config, namespace, identifier), state, ttl)
        if result is False:
            raise RuntimeError("Cache write was rejected.")
    except Exception as error:
        raise CaptchaError("cache_unavailable", "验证码服务暂不可用，请稍后重试。", status_code=503) from error


def take_once(config, namespace, identifier):
    """Atomically claim cached state; a TTL-bound tombstone prevents concurrent replay.

    The backend MUST implement atomic add (Redis SET NX / Memcached add).
    Never delete the tombstone: another reader may already hold the old state.
    """
    cache = caches[config.CACHE_ALIAS]
    key = key_for(config, namespace, identifier)
    try:
        state = cache.get(key)
        now = time.time()
        if not state or state["expires_at"] <= now:
            raise CaptchaError("expired_or_used", "验证码或凭证已过期、已使用，请重新验证。")
        remaining = max(1, math.ceil(state["expires_at"] - now) + 2)
        if not cache.add(key + ":used", True, timeout=remaining):
            raise CaptchaError("expired_or_used", "验证码或凭证已过期、已使用，请重新验证。")
        cache.delete(key)
        return state
    except CaptchaError:
        raise
    except Exception as error:
        raise CaptchaError("cache_unavailable", "验证码服务暂不可用，请稍后重试。", status_code=503) from error
