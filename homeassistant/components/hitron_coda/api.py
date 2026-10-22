"""HTTP client for the Hitron CODA router."""

from http import HTTPStatus

import requests

type DeviceData = dict[str, str | None]


class CannotConnect(Exception):
    """Error communicating with the router."""


class InvalidAuth(Exception):
    """Error authenticating with the router."""


class HitronCodaClient:
    """Read connected devices using the router's web interface."""

    def __init__(
        self, host: str, username: str, password: str, router_type: str
    ) -> None:
        """Initialize the client without performing I/O."""
        self._url = f"http://{host}/data/getConnectInfo.asp"
        self._login_url = f"http://{host}/goform/login"
        self._username = username
        self._password = password
        self._password_field = "pwd" if router_type == "shaw" else "pws"
        self._user_id: str | None = None

    def _login(self) -> None:
        """Authenticate and retain the router's session cookie."""
        try:
            response = requests.post(
                self._login_url,
                data={"user": self._username, self._password_field: self._password},
                timeout=10,
            )
        except requests.RequestException as err:
            raise CannotConnect("Unable to connect to the router") from err
        with response:
            if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise InvalidAuth("The router rejected the credentials")
            if response.status_code != HTTPStatus.OK:
                raise CannotConnect(f"Login failed with HTTP {response.status_code}")
            if not (user_id := response.cookies.get("userid")):
                raise InvalidAuth("The router did not provide a session cookie")
            self._user_id = user_id

    def get_devices(self) -> DeviceData:
        """Return connected clients, retrying an expired session once."""
        if self._user_id is None:
            self._login()
        try:
            return self._get_devices()
        except InvalidAuth:
            self._user_id = None
            self._login()
            return self._get_devices()

    def _get_devices(self) -> DeviceData:
        """Fetch a device list using the current session."""
        try:
            response = requests.get(
                self._url, cookies={"userid": self._user_id}, timeout=10
            )
        except requests.RequestException as err:
            raise CannotConnect("Unable to fetch devices from the router") from err
        with response:
            if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise InvalidAuth("The router session is no longer valid")
            if response.status_code != HTTPStatus.OK:
                raise CannotConnect(
                    f"Device request failed with HTTP {response.status_code}"
                )
            try:
                devices = response.json()
            except ValueError as err:
                raise CannotConnect("Invalid JSON from the router") from err
        if not isinstance(devices, list):
            raise CannotConnect("Invalid device list from the router")
        result: DeviceData = {}
        for device in devices:
            if not isinstance(device, dict):
                raise CannotConnect("Invalid device from the router")
            mac = device.get("macAddr")
            if mac is None:
                continue
            name = device.get("hostName")
            if not isinstance(mac, str) or not (name is None or isinstance(name, str)):
                raise CannotConnect("Invalid device details from the router")
            result[mac.upper()] = name
        return result
