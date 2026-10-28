import hashlib

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle

from .conf import get_config
from .exceptions import CaptchaError


class CaptchaThrottle(SimpleRateThrottle):
    option = "CHALLENGE_RATE"

    def __init__(self):
        config = get_config()
        self.cache = caches[config.CACHE_ALIAS]
        self.prefix = config.KEY_PREFIX
        self.rate = getattr(config, self.option)
        self.num_requests, self.duration = self.parse_rate(self.rate)

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as error:
            raise CaptchaError("cache_unavailable", "验证码服务暂不可用，请稍后重试。", status_code=503) from error

    def get_cache_key(self, request, view):
        # REMOTE_ADDR is deliberately not spoofable using arbitrary forwarded headers.
        ident = hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
        return f"{self.prefix}:rate:{self.option}:{ident}"


class VerifyThrottle(CaptchaThrottle):
    option = "VERIFY_RATE"
