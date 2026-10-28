# DRF Slider CAPTCHA

可直接集成到 **Django REST Framework** 项目的独立应用，为 **rc-slider-captcha** 提供服务端拼图生成与校验 API。

- Pillow 在后端生成背景图、透明拼图；正确位置仅保存在服务端缓存。
- 默认返回 320 × 160 背景与 60 × 160 透明拼图条，不需要把垂直位置暴露给前端。
- 首次有效格式的校验请求即消费题目；位置错误、时长异常也必须重新获取题目。
- 成功后签发短期、一次性 `captchaToken`；登录、注册等业务接口必须再次消费该凭证。
- 用途绑定、可选 IP 绑定、有限数值校验、轨迹长度限制、时长检查、基础限流、禁止 HTTP 缓存。
- 不需要验证码数据库表或迁移；生产环境使用共享 Redis / Memcached。

> 这是自托管的基础反自动化组件，不是身份认证系统，也不是不可破解的人机识别服务。图像匹配和客户端轨迹可以被自动化伪造；高风险业务仍需 MFA、风控和服务端业务限流。

## 1. 本地运行

工作目录：`C:/Users/suqin/Documents/ChatGPT/滑块验证`。

### 后端（终端一）

```powershell
cd "C:/Users/suqin/Documents/ChatGPT/滑块验证"
python -m venv .venv
# PowerShell 禁止运行激活脚本时，无需激活，直接使用虚拟环境 Python。
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

当前系统 Python 已有 Django / DRF / Pillow，也可以直接运行 `python manage.py runserver 127.0.0.1:8000`。

### 前端（终端二）

```powershell
cd "C:/Users/suqin/Documents/ChatGPT/滑块验证/frontend"
npm.cmd ci
npm.cmd run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 将 `/api` 代理到后端，无需开发环境 CORS 配置。

演示账号：`demo`，密码：`demo123!`。三个身份页签只是参考图中的 UI 演示，共用 `login` 用途，不代表实现了法人认证等业务。演示登录只返回成功消息，**不会创建登录会话、JWT 或真实用户**。不要把 `example_project` 作为生产项目部署。

## 2. 集成到已有 DRF 项目

在目标项目的 Python 环境中安装本目录：

```powershell
python -m pip install -e "C:/Users/suqin/Documents/ChatGPT/滑块验证[redis]"
```

也可以构建 wheel 后安装，或将 `drf_slider_captcha` 包复制到项目中。

### settings.py

```python
INSTALLED_APPS += ["drf_slider_captcha"]  # 原项目已经启用 rest_framework

# 生产环境使用专用、共享的 Redis 缓存。地址与密码从环境变量读取。
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

上述片段需要 `import os`，`BASE_DIR` 使用目标项目定义。无需改写目标项目的认证、数据库或用户模型。

### urls.py

```python
from django.urls import include, path

urlpatterns += [path("api/captcha/", include("drf_slider_captcha.urls"))]
```

### 在业务接口消费凭证

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
    # 保留原项目需要的认证、CSRF 和业务限流机制。

    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        consume_captcha_token(
            data.validated_data["captchaToken"],
            purpose="login",  # 服务端固定，不采用客户端提交的用途
            request=request,
        )
        # 然后执行原有账号密码检查、JWT 签发或登录逻辑。
        # 账号密码错误时凭证也已经消费，前端需要重新完成滑块验证。
        return Response({"captchaPassed": True})  # 此处仅展示接入点
```

**不要只信任前端显示的“验证通过”，也不要省略业务接口的 `consume_captcha_token` 调用。** `CaptchaError` 继承 DRF `APIException`，在 DRF view 中自动返回 HTTP 错误。没有公开的 token 消费接口，避免误把消费成功当成业务认证成功。

## 3. API 约定

可导入 Swagger / Apifox 的默认配置文档：`docs/openapi.yaml`。

所有成功结果直接返回 JSON，没有额外的 `data` 包装。生成接口使用 GET，校验接口只接受 JSON POST。路径保留末尾 `/`。

### 获取题目

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

### 校验题目

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

`challengeId`、`x`、`duration` 必填，其余字段可选。`duration` 单位为毫秒。`trail` 是插件采集的浏览器视口 **[x, y] 坐标对**，不是含时间戳的三元组；不使用客户端 `errorCount` 作为后端安全依据。

成功：

```json
{ "success": true, "captchaToken": "随机一次性凭证", "expiresIn": 120 }
```

失败示例（HTTP 400）：

```json
{ "code": "position_mismatch", "message": "拼图位置不匹配，请重试。" }
```

| 错误码 | 含义 |
| --- | --- |
| `invalid_request` | 请求字段错误，附 `errors` 详情；字段错误不消费题目 |
| `expired_or_used` | 题目 / token 已过期、使用或不存在 |
| `position_mismatch` | 超过允许的拼图位置误差 |
| `invalid_motion` | 操作时长或必需轨迹异常 |
| `binding_mismatch` / `binding_required` | IP 绑定不匹配或缺少 request |
| `purpose_mismatch` | token 用于错误业务，该次尝试也消费 token |
| `invalid_token` | 业务请求未提供合理格式的 token |
| `cache_unavailable` | 缓存不可用，HTTP 503，拒绝放行 |

HTTP 429 使用 DRF 原生 `{ "detail": "..." }`，包含 `Retry-After`；JSON 解析 / 方法错误也使用 DRF 原生错误格式。

## 4. rc-slider-captcha 接入

参考 `frontend/src/SliderCaptchaField.tsx`，使用官方发布包 `rc-slider-captcha@1.9.0`。

关键点：

1. `request` Promise 必须返回 `{ bgUrl, puzzleUrl }`，同时保留 `challengeId`。
2. 将服务器 `bgSize` / `puzzleSize` 传给组件。
3. `onVerify` resolve 表示成功，reject 表示失败；HTTP 400 不能当作 resolve。
4. **`VerifyParam.x` 已是拼图移动距离，不要用 `sliderOffsetX` 代替，也不要再次乘滑轨 / 拼图区间比例。**
5. 如果两张图等比缩小，发送 `x / scale`，还原为服务器原图像素。示例用 ResizeObserver 适配窄屏，明确缩放 `bgSize` 和 `puzzleSize`，不用 CSS transform。
6. 成功后将 `captchaToken` 与业务请求一起提交，不放入 URL、不持久化到 localStorage。
7. 题目失败自动刷新；业务失败、token 到期、切换身份都清空 token。`purpose` 改变时使用 `key={purpose}` 重新挂载组件。
8. 可通过项目 CSP 的 `img-src data:` 允许这两张内联图片；生产前端 / API 跨源部署时按实际域名配置 CORS，切勿全开放。

## 5. 配置

`SLIDER_CAPTCHA` 是可选字典；未设置时使用以下默认值。未知配置名称会触发系统检查错误。

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `CACHE_ALIAS` | `default` | Django 缓存别名 |
| `KEY_PREFIX` | `slider-captcha:v1` | 隔离不同应用实例 |
| `WIDTH` / `HEIGHT` | `320` / `160` | 背景原图尺寸 |
| `PIECE_WIDTH` | `60` | 全高透明拼图条宽度 |
| `CHALLENGE_TTL` | `120` | 题目有效秒数，1–3600 |
| `TOKEN_TTL` | `120` | 业务凭证有效秒数，1–3600 |
| `TOLERANCE` | `4` | 原图像素容差，0–10 |
| `MIN_DURATION_MS` / `MAX_DURATION_MS` | `250` / `20000` | 用户单次拖动时长 |
| `MIN_SERVER_ELAPSED_MS` | `200` | 签发题目到校验的服务端最短时长 |
| `REQUIRE_TRAIL` | `False` | 要求至少两个不同的轨迹点；仅基础检查 |
| `MAX_TRAIL_POINTS` | `512` | 轨迹点数量上限 |
| `BIND_IP` | `False` | 同时绑定题目和 token 的 REMOTE_ADDR |
| `PURPOSES` | `login, register, reset_password` | 支持的用途；第一项是默认用途 |
| `BACKGROUND_DIR` | `None` | 本地 JPG / PNG / WebP 图片目录 |
| `CHALLENGE_RATE` / `VERIFY_RATE` | `30/min` / `60/min` | 按 REMOTE_ADDR 的基础限流 |

图片生成使用随机位置和不同拼图轮廓。未配置背景目录时使用内置咖啡 / 书页插画。生产建议放入多张有合法使用权的高纹理照片，避免单色背景或固定模板。目录为空、图片损坏或超出 2500 万像素会报错；部署时先确认图片可读。

## 6. 生产安全与边界

- 使用专用共享 Redis / Memcached，缓存 `add` 必须原子。`DummyCache`、文件缓存和数据库缓存被系统检查拒绝。LocMem 仅开发用，多 worker 不共享题目，且开发缓存驱逐不提供生产保证。
- 单次消费使用原子 `add` 写入“已用”标记，该标记保留至原始有效期之后；即使多个请求已同时读到旧状态，也只能有一个获得消费资格。**保证依赖缓存不提前驱逐标记**：专用 Redis 建议 `maxmemory-policy noeviction`、足够容量；不要读副本或在使用期中途清空缓存。缓存故障会拒绝验证，不降级为放行。
- 内置 DRF 限流是基础流量约束，不是严格并发计数器或 DDoS 防护。生产仍需 Nginx / 网关限流、请求体上限和业务级账户限流。
- 默认只使用 `REMOTE_ADDR`，不信任任意客户端 `X-Forwarded-For`。反向代理下应通过受信基础设施规范化地址，否则所有用户可能被绑定到同一个代理 IP。移动网络换 IP 时不建议开启强制 IP 绑定。
- 开启 HTTPS，使用安全的 `SECRET_KEY`，保护缓存网络和凭证；避免记录 token 和密码。
- 本应用的公开 CAPTCHA API 不采用 SessionAuthentication；业务接口必须保留自己的认证和 CSRF 防护。不要继承演示 `CaptchaAPIView` 来替代真实登录视图安全策略。
- token 仅证明完成过当前 CAPTCHA，不是登录 token、用户 ID 或 MFA 凭证；默认未绑定浏览器身份。需要更强绑定时可在业务层增加签发上下文约束。
- 拼图挑战不是无障碍的唯一认证入口，应为键盘 / 辅助设备使用者提供替代验证流程。

## 7. 测试与构建

```powershell
python manage.py check
python manage.py test tests -v 2
python -m build --wheel --no-isolation
cd frontend
npm.cmd run build
```

当前本地后端 **37 项测试通过**，并完成真实 HTTP 的获取题目 → 校验 → 演示登录 → 拒绝凭证重放检查。前端 TypeScript 检查与 Vite 生产构建通过；未执行浏览器自动拖拽测试或真实 Redis 多进程集成测试。

测试不需要数据库，覆盖图片契约、随机性、容差、输入错误、过期、时长、轨迹、用途 / IP 绑定、缓存故障、限流、登录消费及并发重复校验 / 消费。

依赖范围：Python ≥3.10、Django ≥4.2 / <7、DRF ≥3.15 / <4、Pillow ≥10.4 / <13。当前本地验证环境为 Python 3.13、Django 6.0、DRF 3.17、Pillow 12.2；未声明已经逐一跑过全部版本组合。

## 目录

```text
drf_slider_captcha/    可复用 app（配置、API、图像、一次性缓存、业务消费方法）
example_project/       无数据库依赖的开发项目与演示登录接口
frontend/              Vite + React + TypeScript + rc-slider-captcha 演示
tests/                Django 测试（不创建测试数据库）
```
