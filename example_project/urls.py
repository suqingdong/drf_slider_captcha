from django.urls import include, path

from .views import DemoLoginView

urlpatterns = [
    path("api/captcha/", include("drf_slider_captcha.urls")),
    path("api/demo/login/", DemoLoginView.as_view()),
]
