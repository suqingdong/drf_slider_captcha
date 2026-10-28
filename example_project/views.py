import secrets

from rest_framework import serializers
from rest_framework.response import Response

from drf_slider_captcha.services import consume_captcha_token
from drf_slider_captcha.throttles import VerifyThrottle
from drf_slider_captcha.views import CaptchaAPIView


class DemoLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    captchaToken = serializers.CharField(max_length=128)


class DemoLoginView(CaptchaAPIView):
    """Demo ONLY: does not create sessions or issue actual auth credentials."""
    throttle_classes = [VerifyThrottle]

    def post(self, request):
        data = self.validate(DemoLoginSerializer(data=request.data))
        consume_captcha_token(data["captchaToken"], purpose="login", request=request)
        if not (secrets.compare_digest(data["username"].encode("utf-8"), b"demo")
                and secrets.compare_digest(data["password"].encode("utf-8"), b"demo123!")):
            return Response({"code": "invalid_credentials", "message": "演示账号或密码错误，请重新完成验证。"}, status=400)
        return Response({"success": True, "message": "验证码凭证已消费，演示登录成功。", "user": {"username": "demo"}})
