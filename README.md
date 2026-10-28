# DRF Slider CAPTCHA

English | [简体中文](https://github.com/suqingdong/drf_slider_captcha/blob/master/README.zh-CN.md)

A **Django REST Framework** app providing puzzle generation and verification APIs for **rc-slider-captcha**, with short-lived, single-use tokens for login, registration, and other protected endpoints.

> CAPTCHA is an anti-automation aid, not authentication or a replacement for MFA and rate limiting.

## 1. Run locally

All commands below start from the project root, which contains `manage.py` and `pyproject.toml`. Open both terminals in that directory.

### Backend (terminal 1)

```powershell
python -m venv .venv
# If PowerShell blocks activation scripts, call the virtual environment's Python directly.
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

If your Python environment already has Django / DRF / Pillow installed, you can also run `python manage.py runserver 127.0.0.1:8000` directly.

### Frontend (terminal 2)

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173` in your browser. Vite proxies `/api` to the backend, so no development CORS configuration is needed.

Demo username: `demo`; password: `demo123!`. The three identity tabs are UI demonstrations based on the reference design. They all use the `login` purpose and do not implement corporate identity verification or other identity-specific workflows. The demo login returns only a success message; it **does not create a login session, JWT, or real user**. Do not deploy `example_project` as your production project.

## 2. Integrate into an existing DRF project

Install the package from PyPI in your DRF project's Python environment:

```powershell
python -m pip install "drf-slider-captcha[redis]"
```

### settings.py

```python
INSTALLED_APPS += ["drf_slider_captcha"]  # rest_framework is already enabled in your project.

# Use a dedicated, shared Redis cache in production. Read its URL and credentials from the environment.
CACHES["slider_captcha"] = {
    "BACKEND": "django.core.cache.backends.redis.RedisCache",
    "LOCATION": os.environ["CAPTCHA_REDIS_URL"],
}
SLIDER_CAPTCHA = {
    "CACHE_ALIAS": "slider_captcha",
    "CHALLENGE_TTL": 120,
    "TOKEN_TTL": 120,
    "TOLERANCE": 4,
    "PURPOSES": ["login", "register", "reset_password"],
    # "BACKGROUND_DIR": BASE_DIR / "captcha_backgrounds",
    # "BIND_IP": True,
}
```

This snippet requires `import os` and your target project's existing `BASE_DIR`. You do not need to replace its authentication, database configuration, or user model.

### urls.py

```python
from django.urls import include, path

urlpatterns += [path("api/captcha/", include("drf_slider_captcha.urls"))]
```

### Consume the token in your business endpoint

```python
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_slider_captcha.services import consume_captcha_token

class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    captchaToken = serializers.CharField(max_length=128)

class LoginView(APIView):
    permission_classes = [AllowAny]
    # Preserve your project's authentication, CSRF protection, and business rate limits.

    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        consume_captcha_token(
            data.validated_data["captchaToken"],
            purpose="login",  # Fix the purpose on the server; do not accept it from the client.
            request=request,
        )
        # Continue with your existing password checks, JWT issuance, or login logic.
        # Even if the credentials are wrong, the token has been consumed;
        # the frontend must require a new CAPTCHA.
        return Response({"captchaPassed": True})  # Integration example only.
```

**Do not trust the frontend's “verification passed” state, and do not omit `consume_captcha_token` from the protected business endpoint.** `CaptchaError` extends DRF's `APIException`, so a DRF view automatically returns an HTTP error. There is no public token-consumption endpoint: successful token consumption must not be confused with successful business authentication.

## 3. API contract

The default OpenAPI document, `docs/openapi.yaml`, can be imported into Swagger / Apifox.

Successful responses return JSON directly, without an extra `data` wrapper. Challenge generation uses GET; verification accepts only JSON POST. Keep the trailing `/` in endpoint paths.

### Get a challenge

`GET /api/captcha/challenge/?purpose=login`

```json
{
  "challengeId": "48d87b03-e2d8-4cac-adc9-d04c9b80cb47",
  "bgUrl": "data:image/jpeg;base64,...",
  "puzzleUrl": "data:image/png;base64,...",
  "bgSize": { "width": 320, "height": 160 },
  "puzzleSize": { "width": 60, "height": 160, "top": 0, "left": 0 },
  "expiresIn": 120,
  "purpose": "login"
}
```

### Verify a challenge

`POST /api/captcha/verify/`

```json
{
  "challengeId": "48d87b03-e2d8-4cac-adc9-d04c9b80cb47",
  "x": 185.4,
  "duration": 825,
  "y": 2,
  "sliderOffsetX": 202,
  "trail": [[80, 350], [110, 351], [185, 352]],
  "targetType": "button",
  "errorCount": 0
}
```

`challengeId`, `x`, and `duration` are required; the remaining fields are optional. `duration` is measured in milliseconds. `trail` contains browser-viewport **[x, y] coordinate pairs** collected by the plugin, not timestamped triples. The backend does not use the client-provided `errorCount` as a security signal.

Success:

```json
{ "success": true, "captchaToken": "<opaque-single-use-token>", "expiresIn": 120 }
```

Example failure (HTTP 400):

```json
{ "code": "position_mismatch", "message": "拼图位置不匹配，请重试。" }
```

Human-readable CAPTCHA error messages are currently returned in Chinese. Use the stable `code` values for client-side logic and localization rather than matching message text.

| Error code | Meaning |
| --- | --- |
| `invalid_request` | Invalid request fields, with details in `errors`; field-validation errors do not consume the challenge |
| `expired_or_used` | The challenge / token has expired, has already been used, or does not exist |
| `position_mismatch` | The puzzle position exceeds the allowed tolerance |
| `invalid_motion` | Invalid duration or required trajectory |
| `binding_mismatch` / `binding_required` | IP binding does not match, or the required request context is missing |
| `purpose_mismatch` | The token is used for the wrong business purpose; this attempt also consumes the token |
| `invalid_token` | The business request does not provide a reasonably formatted token |
| `cache_unavailable` | The cache is unavailable; HTTP 503, verification fails closed |

HTTP 429 uses DRF's standard `{ "detail": "..." }` response and includes `Retry-After`. JSON parse errors and unsupported methods also use DRF's standard error format.

## 4. Integrate rc-slider-captcha

See `frontend/src/SliderCaptchaField.tsx`, which uses the official published package `rc-slider-captcha@1.9.0`.

Key points:

1. The `request` Promise must return `{ bgUrl, puzzleUrl }`; retain `challengeId` separately.
2. Pass the server's `bgSize` / `puzzleSize` to the component.
3. Resolve `onVerify` for success and reject it for failure. An HTTP 400 response must not resolve the Promise.
4. **`VerifyParam.x` is already the puzzle displacement. Do not replace it with `sliderOffsetX` or multiply it again by a slider-track / puzzle-range ratio.**
5. If both images are scaled down proportionally, send `x / scale` to restore server-image pixels. The demo uses ResizeObserver for narrow screens and explicitly scales `bgSize` and `puzzleSize`, rather than applying a CSS transform.
6. Submit `captchaToken` with the business request after verification. Do not put it in URLs or persist it in localStorage.
7. Refresh the challenge automatically after verification failure. Clear the token after business failure, token expiry, or an identity-tab change. Remount the component with `key={purpose}` when the purpose changes.
8. Allow the two inline images with `img-src data:` in your project's CSP. If the production frontend and API use different origins, configure CORS for the actual domains instead of allowing all origins.

## 5. Configuration

`SLIDER_CAPTCHA` is an optional dictionary. The following defaults apply when it is not configured. Unknown setting names trigger a Django system-check error.

| Setting | Default | Description |
| --- | --- | --- |
| `CACHE_ALIAS` | `default` | Django cache alias |
| `KEY_PREFIX` | `slider-captcha:v1` | Isolates different application instances |
| `WIDTH` / `HEIGHT` | `320` / `160` | Native background-image dimensions |
| `PIECE_WIDTH` | `60` | Width of the full-height transparent puzzle strip |
| `CHALLENGE_TTL` | `120` | Challenge lifetime in seconds, 1–3600 |
| `TOKEN_TTL` | `120` | Business token lifetime in seconds, 1–3600 |
| `TOLERANCE` | `4` | Position tolerance in native-image pixels, 0–10 |
| `MIN_DURATION_MS` / `MAX_DURATION_MS` | `250` / `20000` | Duration of a single drag in milliseconds |
| `MIN_SERVER_ELAPSED_MS` | `200` | Minimum server-side time between challenge issuance and verification, in milliseconds |
| `REQUIRE_TRAIL` | `False` | Requires at least two distinct trajectory points; a basic check only |
| `MAX_TRAIL_POINTS` | `512` | Maximum number of trajectory points |
| `BIND_IP` | `False` | Binds both challenges and tokens to REMOTE_ADDR |
| `PURPOSES` | `login, register, reset_password` | Allowed purposes; the first entry is the default |
| `BACKGROUND_DIR` | `None` | Local directory of JPG / PNG / WebP background images |
| `CHALLENGE_RATE` / `VERIFY_RATE` | `30/min` / `60/min` | Basic rate limits by REMOTE_ADDR |

Image generation randomizes the puzzle position and profile. Without a background directory, it uses the built-in coffee / notebook illustration. For production, supply multiple legally usable, texture-rich photographs and avoid flat-color backgrounds or fixed templates. An empty directory, a corrupt image, or an image exceeding 25 million pixels causes an error; confirm that your images are readable before deployment.

## 6. Production security and limitations

- Use dedicated shared Redis / Memcached with atomic cache `add`. System checks reject `DummyCache`, file-based caches, and database caches. LocMem is for development only: workers do not share challenges, and development-cache eviction does not provide production guarantees.
- Single-use consumption uses atomic `add` to write a “used” marker that remains beyond the original expiry. Even if several requests have already read the old state, only one can claim the right to consume it. **This guarantee depends on markers not being evicted early**: use a dedicated Redis instance with sufficient capacity and preferably `maxmemory-policy noeviction`. Do not read replicas or clear the cache during a token's lifetime. Cache failures reject verification instead of allowing requests through.
- Built-in DRF throttling provides basic traffic limits, not strict concurrent counters or DDoS protection. Production still needs Nginx / gateway rate limits, request-body limits, and account-level business throttling.
- By default, only `REMOTE_ADDR` is used; arbitrary client-supplied `X-Forwarded-For` headers are not trusted. Behind a reverse proxy, normalize addresses through trusted infrastructure; otherwise, all users may be bound to the same proxy IP. Strong IP binding is not recommended when mobile-network addresses may change.
- Enable HTTPS, use a secure `SECRET_KEY`, protect the cache network and credentials, and avoid logging tokens or passwords.
- The public CAPTCHA APIs do not use SessionAuthentication. Your business endpoints must retain their own authentication and CSRF protections. Do not inherit the demo `CaptchaAPIView` as a replacement for your real login view's security policy.
- A token proves only that the current CAPTCHA was completed. It is not a login token, user ID, or MFA credential, and is not bound to browser identity by default. Add issuance-context constraints in the business layer if stronger binding is needed.
- A puzzle challenge must not be the only accessible authentication route. Provide an alternative verification flow for keyboard and assistive-technology users.
