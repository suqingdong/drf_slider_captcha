from rest_framework.exceptions import APIException


class CaptchaError(APIException):
    status_code = 400

    def __init__(self, code, message, *, status_code=400, errors=None):
        self.status_code = status_code
        detail = {"code": code, "message": message}
        if errors is not None:
            detail["errors"] = errors
        super().__init__(detail=detail, code=code)
