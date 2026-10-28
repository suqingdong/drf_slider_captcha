from django.urls import path

from .views import ChallengeView, VerifyView

app_name = "slider_captcha"
urlpatterns = [
    path("challenge/", ChallengeView.as_view(), name="challenge"),
    path("verify/", VerifyView.as_view(), name="verify"),
]
