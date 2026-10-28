import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import tempfile
import time
from unittest.mock import patch
import uuid

from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from drf_slider_captcha.checks import check_captcha_settings
from drf_slider_captcha.conf import get_config
from drf_slider_captcha.exceptions import CaptchaError
from drf_slider_captcha.images import generate_puzzle
from drf_slider_captcha.services import consume_captcha_token, create_challenge, verify_challenge
from drf_slider_captcha.storage import key_for, store


@override_settings(DEBUG=True)
class CaptchaTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        caches["default"].clear()

    def challenge(self, **params):
        response = self.client.get("/api/captcha/challenge/", params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def answer_payload(self, challenge=None, **overrides):
        challenge = challenge or self.challenge()
        config = get_config()
        key = key_for(config, "challenge", challenge["challengeId"])
        state = caches["default"].get(key)
        state["created_at"] = time.time() - 1.5
        caches["default"].set(key, state, 120)
        data = {"challengeId": challenge["challengeId"], "x": state["answer"], "duration": 800,
                "y": 0, "sliderOffsetX": 180, "trail": [[12, 30], [80, 30], [190, 31]],
                "targetType": "button", "errorCount": 0}
        data.update(overrides)
        return data

    def token(self, **params):
        response = self.client.post("/api/captcha/verify/", self.answer_payload(self.challenge(**params)), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["captchaToken"]

    def test_challenge_contract_and_images(self):
        data = self.challenge()
        self.assertEqual(data["purpose"], "login")
        self.assertEqual(data["bgSize"], {"width": 320, "height": 160})
        self.assertNotIn("answer", data)
        self.assertNotIn("x", data)
        uuid.UUID(data["challengeId"])
        for field, size, mode in (("bgUrl", (320, 160), "RGB"), ("puzzleUrl", (60, 160), "RGBA")):
            with Image.open(BytesIO(base64.b64decode(data[field].split(",")[1]))) as image:
                self.assertEqual(image.size, size)
                self.assertEqual(image.mode, mode)
                if mode == "RGBA":
                    self.assertEqual(image.getpixel((0, 0))[3], 0)
                    self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_challenge_no_store_headers(self):
        response = self.client.get("/api/captcha/challenge/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_random_challenges(self):
        first, second = self.challenge(), self.challenge()
        self.assertNotEqual(first["challengeId"], second["challengeId"])
        self.assertNotEqual(first["bgUrl"], second["bgUrl"])

    def test_unknown_purpose(self):
        response = self.client.get("/api/captcha/challenge/", {"purpose": "admin"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_request")

    def test_success_returns_opaque_token_without_answer(self):
        response = self.client.post("/api/captcha/verify/", self.answer_payload(), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["captchaToken"]), 43)
        self.assertNotIn("answer", response.data)

    def test_tolerance_boundary(self):
        data = self.answer_payload()
        data["x"] += get_config().TOLERANCE
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").status_code, 200)

    def test_wrong_position_consumes_challenge(self):
        data = self.answer_payload()
        response = self.client.post("/api/captcha/verify/", {**data, "x": 0}, format="json")
        self.assertEqual(response.data["code"], "position_mismatch")
        replay = self.client.post("/api/captcha/verify/", data, format="json")
        self.assertEqual(replay.data["code"], "expired_or_used")

    def test_success_cannot_be_replayed(self):
        data = self.answer_payload()
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").data["code"], "expired_or_used")

    def test_missing_challenge(self):
        response = self.client.post("/api/captcha/verify/", {"challengeId": str(uuid.uuid4()), "x": 100, "duration": 800}, format="json")
        self.assertEqual(response.data["code"], "expired_or_used")

    def test_expired_challenge_even_if_cache_still_contains_it(self):
        data = self.answer_payload()
        config = get_config()
        key = key_for(config, "challenge", data["challengeId"])
        state = caches["default"].get(key)
        state["expires_at"] = time.time() - 1
        caches["default"].set(key, state, 60)
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").data["code"], "expired_or_used")

    def test_malformed_inputs(self):
        for field, value in [("challengeId", "bad"), ("x", "nan"), ("x", "inf"), ("x", True),
                             ("x", -1), ("duration", -1), ("trail", [[1, 2, 3]]), ("trail", [["nan", 0]]),
                             ("targetType", "robot")]:
            with self.subTest(field=field, value=value):
                data = self.answer_payload()
                data[field] = value
                response = self.client.post("/api/captcha/verify/", data, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], "invalid_request")

    def test_large_trail_is_rejected(self):
        data = self.answer_payload(trail=[[1, 2]] * 513)
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").data["code"], "invalid_request")

    def test_duration_bounds(self):
        for duration in [0, 249, 20001]:
            data = self.answer_payload(duration=duration)
            self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").data["code"], "invalid_motion")

    def test_server_elapsed_time_cannot_be_spoofed(self):
        challenge = self.challenge()
        key = key_for(get_config(), "challenge", challenge["challengeId"])
        state = caches["default"].get(key)
        data = {"challengeId": challenge["challengeId"], "x": state["answer"], "duration": 800}
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").data["code"], "invalid_motion")

    @override_settings(SLIDER_CAPTCHA={"REQUIRE_TRAIL": True})
    def test_required_trail(self):
        for trail in [[], [[1, 2]], [[1, 2], [1, 2]]]:
            response = self.client.post("/api/captcha/verify/", self.answer_payload(trail=trail), format="json")
            self.assertEqual(response.data["code"], "invalid_motion")
        self.assertEqual(self.client.post("/api/captcha/verify/", self.answer_payload(), format="json").status_code, 200)

    def test_token_is_one_time_and_hashed_in_cache(self):
        token = self.token()
        self.assertNotIn(token, key_for(get_config(), "token", token))
        self.assertTrue(consume_captcha_token(token, purpose="login"))
        with self.assertRaises(CaptchaError) as error:
            consume_captcha_token(token, purpose="login")
        self.assertEqual(error.exception.detail["code"], "expired_or_used")

    def test_wrong_purpose_consumes_token(self):
        token = self.token(purpose="register")
        with self.assertRaises(CaptchaError) as error:
            consume_captcha_token(token, purpose="login")
        self.assertEqual(error.exception.detail["code"], "purpose_mismatch")
        with self.assertRaises(CaptchaError):
            consume_captcha_token(token, purpose="register")

    def test_expired_token(self):
        token = self.token()
        config = get_config()
        store(config, "token", token, {"purpose": "login", "binding": "", "expires_at": time.time()-1}, 60)
        with self.assertRaises(CaptchaError):
            consume_captcha_token(token, purpose="login")

    def test_invalid_tokens(self):
        for token in [None, "", "guess", 42, "x"*129]:
            with self.assertRaises(CaptchaError):
                consume_captcha_token(token, purpose="login")

    @override_settings(SLIDER_CAPTCHA={"BIND_IP": True})
    def test_challenge_ip_binding(self):
        data = self.answer_payload()
        response = self.client.post("/api/captcha/verify/", data, format="json", REMOTE_ADDR="192.0.2.7")
        self.assertEqual(response.data["code"], "binding_mismatch")

    @override_settings(SLIDER_CAPTCHA={"BIND_IP": True})
    def test_token_ip_binding(self):
        token = self.token()
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().post("/", REMOTE_ADDR="192.0.2.7")
        with self.assertRaises(CaptchaError) as error:
            consume_captcha_token(token, purpose="login", request=request)
        self.assertEqual(error.exception.detail["code"], "binding_mismatch")

    @override_settings(SLIDER_CAPTCHA={"BIND_IP": True})
    def test_binding_requires_request(self):
        with self.assertRaises(CaptchaError):
            create_challenge(purpose="login")

    def test_concurrent_token_consumption_has_exactly_one_winner(self):
        token = self.token()
        def attempt(_):
            try:
                consume_captcha_token(token, purpose="login")
                return True
            except CaptchaError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(16))), 1)

    def test_concurrent_challenge_verification_has_exactly_one_winner(self):
        data = self.answer_payload()
        def attempt(_):
            try:
                verify_challenge(data)
                return True
            except CaptchaError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(16))), 1)

    @override_settings(SLIDER_CAPTCHA={"CHALLENGE_RATE": "2/min"})
    def test_challenge_throttling_and_forwarded_header_spoofing(self):
        self.challenge()
        self.challenge()
        response = self.client.get("/api/captcha/challenge/", HTTP_X_FORWARDED_FOR="192.0.2.44")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(SLIDER_CAPTCHA={"VERIFY_RATE": "1/min"})
    def test_verification_throttling(self):
        data = self.answer_payload()
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/captcha/verify/", data, format="json").status_code, 429)

    def test_cache_outage_returns_503(self):
        with patch.object(caches["default"], "get", side_effect=ConnectionError("down")):
            response = self.client.get("/api/captcha/challenge/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "cache_unavailable")

    def test_demo_login_consumes_token(self):
        data = {"username": "demo", "password": "demo123!", "captchaToken": self.token()}
        self.assertEqual(self.client.post("/api/demo/login/", data, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/demo/login/", data, format="json").data["code"], "expired_or_used")

    def test_demo_wrong_password_requires_new_token(self):
        data = {"username": "demo", "password": "wrong", "captchaToken": self.token()}
        self.assertEqual(self.client.post("/api/demo/login/", data, format="json").data["code"], "invalid_credentials")
        data["password"] = "demo123!"
        self.assertEqual(self.client.post("/api/demo/login/", data, format="json").data["code"], "expired_or_used")

    def test_demo_non_ascii_credentials_return_400(self):
        data = {"username": "测试账号", "password": "测试密码", "captchaToken": self.token()}
        self.assertEqual(self.client.post("/api/demo/login/", data, format="json").status_code, 400)

    def test_cache_rejected_write_fails_closed(self):
        with patch.object(caches["default"], "set", return_value=False):
            with self.assertRaises(CaptchaError) as error:
                create_challenge(purpose="login")
        self.assertEqual(error.exception.status_code, 503)

    def test_missing_required_fields(self):
        response = self.client.post("/api/captcha/verify/", {}, format="json")
        self.assertEqual(response.data["code"], "invalid_request")
        self.assertEqual(set(response.data["errors"]), {"challengeId", "x", "duration"})

    def test_config_checks(self):
        self.assertEqual(check_captcha_settings(None), [])
        for raw in [{"WIDTH": 100}, {"CHALLENGE_TTL": 0}, {"TOKEN_TTL": 3601}, {"TOLERANCE": float("nan")},
                    {"TYPO": True}, {"PURPOSES": []}, {"MAX_TRAIL_POINTS": 1}, {"BIND_IP": "false"},
                    {"CACHE_ALIAS": "missing"}, {"CHALLENGE_RATE": 123}]:
            with self.subTest(raw=raw), override_settings(SLIDER_CAPTCHA=raw):
                with self.assertRaises(ImproperlyConfigured):
                    get_config()
        with override_settings(SLIDER_CAPTCHA={"CHALLENGE_RATE": "oops"}):
            self.assertEqual(check_captcha_settings(None)[0].id, "slider_captcha.E001")
        with override_settings(DEBUG=False):
            self.assertEqual(check_captcha_settings(None)[0].id, "slider_captcha.W001")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
    def test_non_atomic_backend_check(self):
        self.assertEqual(check_captcha_settings(None)[0].id, "slider_captcha.E002")

    def test_custom_local_background(self):
        with tempfile.TemporaryDirectory() as directory:
            Image.new("RGB", (640, 300), "#123456").save(directory + "/photo.png")
            with override_settings(SLIDER_CAPTCHA={"BACKGROUND_DIR": directory}):
                self.challenge()

    def test_empty_background_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(SLIDER_CAPTCHA={"BACKGROUND_DIR": directory}):
                with self.assertRaises(ImproperlyConfigured):
                    generate_puzzle(get_config())

    def test_custom_dimensions(self):
        with override_settings(SLIDER_CAPTCHA={"WIDTH": 360, "HEIGHT": 180, "PIECE_WIDTH": 64}):
            data = self.challenge()
            self.assertEqual(data["bgSize"], {"width": 360, "height": 180})
            self.assertEqual(data["puzzleSize"]["width"], 64)
            self.assertEqual(self.client.post("/api/captcha/verify/", self.answer_payload(data), format="json").status_code, 200)
