import hashlib
import hmac
import secrets
import time
import uuid

from django.conf import settings

from .conf import get_config
from .exceptions import CaptchaError
from .images import generate_puzzle
from .storage import store, take_once


def _binding(config, request):
    if not config.BIND_IP:
        return ""
    if request is None:
        raise CaptchaError("binding_required", "开启 IP 绑定时必须传入有效客户端地址的 request。")
    # Do not trust user-supplied X-Forwarded-For. Configure REMOTE_ADDR at the trusted proxy.
    address = request.META.get("REMOTE_ADDR", "")
    if not address:
        raise CaptchaError("binding_required", "开启 IP 绑定时必须传入有效客户端地址的 request。")
    return hmac.new(settings.SECRET_KEY.encode(), address.encode(), hashlib.sha256).hexdigest()


def create_challenge(*, purpose, request=None):
    config = get_config()
    if purpose not in config.PURPOSES:
        raise CaptchaError("invalid_purpose", "不支持的验证码用途。")
    binding = _binding(config, request)
    images, answer = generate_puzzle(config)
    identifier = str(uuid.uuid4())
    now = time.time()
    state = {"answer": answer, "purpose": purpose, "binding": binding,
             "created_at": now, "expires_at": now + config.CHALLENGE_TTL}
    store(config, "challenge", identifier, state, config.CHALLENGE_TTL)
    return {"challengeId": identifier, **images,
            "bgSize": {"width": config.WIDTH, "height": config.HEIGHT},
            "puzzleSize": {"width": config.PIECE_WIDTH, "height": config.HEIGHT, "top": 0, "left": 0},
            "expiresIn": config.CHALLENGE_TTL, "purpose": purpose}


def verify_challenge(data, *, request=None):
    """Accept validated VerifySerializer data in native image pixels."""
    config = get_config()
    state = take_once(config, "challenge", str(data["challengeId"]))
    if not hmac.compare_digest(state["binding"], _binding(config, request)):
        raise CaptchaError("binding_mismatch", "客户端已变化，请重新验证。")
    elapsed_ms = (time.time() - state["created_at"]) * 1000
    duration = data["duration"]
    if (duration < config.MIN_DURATION_MS or duration > config.MAX_DURATION_MS
            or elapsed_ms < config.MIN_SERVER_ELAPSED_MS
            or duration > elapsed_ms + 1000):
        raise CaptchaError("invalid_motion", "操作时长或轨迹异常，请重新拖动验证。")
    trail = data.get("trail", [])
    if config.REQUIRE_TRAIL:
        # rc-slider-captcha trail points are viewport coordinates, NOT x/y/time triples.
        if len(trail) < 2 or len({tuple(point) for point in trail}) < 2:
            raise CaptchaError("invalid_motion", "操作时长或轨迹异常，请重新拖动验证。")
    if abs(data["x"] - state["answer"]) > config.TOLERANCE:
        raise CaptchaError("position_mismatch", "拼图位置不匹配，请重试。")
    token = secrets.token_urlsafe(32)
    now = time.time()
    store(config, "token", token, {"purpose": state["purpose"], "binding": state["binding"],
                                  "expires_at": now + config.TOKEN_TTL}, config.TOKEN_TTL)
    return {"success": True, "captchaToken": token, "expiresIn": config.TOKEN_TTL}


def consume_captcha_token(token, *, purpose, request=None):
    """Call ONLY in a protected business endpoint, before performing its side effect.

    Every attempt consumes the credential, including wrong-purpose/binding attempts.
    No public consume endpoint is intentionally exposed.
    """
    if not isinstance(token, str) or not 20 <= len(token) <= 128:
        raise CaptchaError("invalid_token", "请先完成滑块验证。")
    config = get_config()
    state = take_once(config, "token", token)
    if state["purpose"] != purpose:
        raise CaptchaError("purpose_mismatch", "验证码凭证不能用于此操作。")
    if not hmac.compare_digest(state["binding"], _binding(config, request)):
        raise CaptchaError("binding_mismatch", "客户端已变化，请重新验证。")
    return True
