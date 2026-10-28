from django.utils.cache import patch_cache_control
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import CaptchaError
from .serializers import ChallengeSerializer, VerifySerializer
from .services import create_challenge, verify_challenge
from .throttles import CaptchaThrottle, VerifyThrottle


class CaptchaAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_cache_control(response, no_store=True, private=True, max_age=0)
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def validate(self, serializer):
        if not serializer.is_valid():
            raise CaptchaError("invalid_request", "请求参数不正确。", errors=serializer.errors)
        return serializer.validated_data


class ChallengeView(CaptchaAPIView):
    throttle_classes = [CaptchaThrottle]

    def get(self, request):
        data = self.validate(ChallengeSerializer(data=request.query_params))
        return Response(create_challenge(purpose=data["purpose"], request=request))


class VerifyView(CaptchaAPIView):
    throttle_classes = [VerifyThrottle]

    def post(self, request):
        data = self.validate(VerifySerializer(data=request.data))
        return Response(verify_challenge(data, request=request))
