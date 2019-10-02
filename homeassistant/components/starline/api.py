import hashlib
import requests
from typing import Dict, List, Callable, Optional, Any

from .device import StarlineDevice
from .const import LOGGER, ENCODING, GET, POST, CONNECT_TIMEOUT, READ_TIMEOUT


class BaseApi:
    """Base StarLine API."""

    def __init__(self):
        """Constructor."""
        self._session = requests.Session()

    def request(self, method: str, url: str, params: dict = None, data: dict = None, json: dict = None, headers: dict = None) -> requests.Response:
        """Make request."""

        response = self._session.request(method, url, params=params, data=data, json=json, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        response.encoding = ENCODING

        LOGGER.debug("StarlineApi {} request: {}".format(method, url))
        LOGGER.debug("  Payload: {}".format(params))
        LOGGER.debug("  Data: {}".format(data))
        LOGGER.debug("  JSON: {}".format(json))
        LOGGER.debug("  Headers: {}".format(headers))
        LOGGER.debug("  Response: {}".format(response))

        # TODO: Handle Exceptions
        return response

    def get(self, url: str, params: dict = None, headers: dict = None) -> dict:
        """Make GET request."""

        response = self.request(GET, url, params=params, headers=headers)
        data = response.json()
        LOGGER.debug("  Data: {}".format(data))
        return data

    def post(self, url: str, params: dict = None, data: dict = None, json: dict = None, headers: dict = None) -> dict:
        """Make POST request."""

        response = self.request(POST, url, params=params, data=data, json=json, headers=headers)
        data = response.json()
        LOGGER.debug("  Data: {}".format(data))
        return data


class StarlineAuth(BaseApi):
    """Auth API."""

    def get_app_code(self, app_id: str, app_secret: str) -> dict:
        """Get application code for getting application token."""

        url = "https://id.starline.ru/apiV3/application/getCode/"
        payload = {
            "appId": app_id,
            "secret": hashlib.md5(app_secret.encode(ENCODING)).hexdigest()
        }
        response = self.get(url, params=payload)

        if int(response["state"]) == 1:
            app_code = response["desc"]["code"]
            LOGGER.debug("Application code: {}".format(app_code))
            return app_code
        raise Exception(response)

    def get_app_token(self, app_id: str, app_secret: str, app_code: str) -> dict:
        """Get application token for authentication."""

        url = "https://id.starline.ru/apiV3/application/getToken/"
        payload = {
            "appId": app_id,
            "secret": hashlib.md5((app_secret + app_code).encode(ENCODING)).hexdigest()
        }
        response = self.get(url, params=payload)

        if int(response["state"]) == 1:
            app_token = response["desc"]["token"]
            LOGGER.debug("Application token: {}".format(app_token))
            return app_token
        raise Exception(response)

    def get_slid_user_token(self, app_token: str, user_login: str, user_password: str, sms_code: str = None, captcha_sid: str = None, captcha_code:str = None) -> (bool, dict):
        """Authenticate user by login, password and application token."""

        url = "https://id.starline.ru/apiV3/user/login/"
        payload = {
            "token": app_token
        }
        data = {
            "login": user_login,
            "pass": hashlib.sha1(user_password.encode(ENCODING)).hexdigest()
        }
        if sms_code is not None:
            data["smsCode"] = sms_code
        if (captcha_sid is not None) and (captcha_code is not None):
            data["captchaSid"] = captcha_sid
            data["captchaCode"] = captcha_code
        response = self.post(url, params=payload, data=data)

        state = int(response["state"])
        if (state == 1) or (state == 2) or (state == 0 and "captchaSid" in response["desc"]) or (state == 0 and "phone" in response["desc"]):
            return state == 1, response["desc"]
        raise Exception(response)

    def get_user_id(self, slid_token: str) -> (str, str):
        """Authenticate user by StarLineID token."""

        url = "https://developer.starline.ru/json/v2/auth.slid"
        data = {
            "slid_token": slid_token
        }
        response = self.request(POST, url, json=data)
        json = response.json()

        # TODO: check response code
        slnet_token = response.cookies["slnet"]
        LOGGER.debug("SLnet token: {}".format(slnet_token))
        return slnet_token, json["user_id"]


class StarlineApi(BaseApi):
    """Data API."""

    def __init__(self, user_id: str, slnet_token: str):
        """Constructor."""
        super().__init__()
        self._user_id = user_id
        self._slnet_token = slnet_token
        self._devices: Dict[str, StarlineDevice] = {}
        self._update_listeners: List[Callable] = []

    def add_update_listener(self, listener: Callable) -> None:
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)

    def _call_listeners(self) -> None:
        """Call listeners for update notifications."""
        for listener in self._update_listeners:
            listener()

    def update(self, now=None) -> None:
        """Update StarLine data."""
        devices = self.get_user_info()

        for device_data in devices:
            device_id = device_data["device_id"]
            if device_id not in self._devices:
                self._devices[device_id] = StarlineDevice()
            self._devices[device_id].update(device_data)

        self._call_listeners()

    @property
    def devices(self):
        """Devices list."""
        return self._devices

    def get_user_info(self) -> Optional[List[Dict[str, Any]]]:
        """Get user information."""

        url = "https://developer.starline.ru/json/v2/user/{}/user_info".format(self._user_id)
        headers = {"Cookie": "slnet=" + self._slnet_token}
        response = self.get(url, headers=headers)

        code = int(response["code"])
        if code == 200:
            return response["devices"] + response["shared_devices"]
        return None

    def _set_param(self, device_id: str, name: str, value: Any):
        url = "https://developer.starline.ru/json/v1/device/{}/set_param".format(device_id)
        data = {
            "type": name,
            name: value,
        }
        headers = {"Cookie": "slnet=" + self._slnet_token}
        response = self.post(url, json=data, headers=headers)

        code = int(response["code"])
        if code == 200:
            return response
        return None

    def set_arm_state(self, device_id: str, state: bool) -> None:
        """Set security state."""
        response = self._set_param(device_id, "arm", 1 if state else 0)
        if response is not None:
            self._devices[device_id].update_car_state(response)
            self._call_listeners()
