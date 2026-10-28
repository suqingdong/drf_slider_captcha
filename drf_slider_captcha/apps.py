from django.apps import AppConfig


class SliderCaptchaConfig(AppConfig):
    name = "drf_slider_captcha"
    verbose_name = "Slider CAPTCHA"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import checks  # noqa: F401
