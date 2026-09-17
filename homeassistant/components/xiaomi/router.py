"""Synchronous client for the Xiaomi Mi router web API.

All network calls are blocking and must be run in the executor.
"""

from http import HTTPStatus
import logging
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

LOGIN_TIMEOUT = 5
LIST_TIMEOUT = 10


class XiaomiConnectionError(Exception):
    """Raised when the router cannot be reached or replies invalidly."""


class XiaomiTimeoutError(XiaomiConnectionError):
    """Raised when a request to the router times out."""


class XiaomiAuthError(Exception):
    """Raised when the router rejects the credentials or token."""


class XiaomiClient:
    """Talk to the Xiaomi Mi router web API."""

    def __init__(self, host: str, username: str, password: str) -> None:
        """Initialize the client."""
        self.host = host
        self.username = username
        self.password = password
        self.token: str | None = None

    def login(self) -> None:
        """Log in to the router and store the token, raising on failure."""
        url = f"http://{self.host}/cgi-bin/luci/api/xqsystem/login"
        try:
            res = requests.post(
                url,
                data={"username": self.username, "password": self.password},
                timeout=LOGIN_TIMEOUT,
            )
        except requests.exceptions.Timeout as err:
            raise XiaomiTimeoutError from err
        except requests.exceptions.ConnectionError as err:
            raise XiaomiConnectionError from err

        if res.status_code == HTTPStatus.UNAUTHORIZED:
            raise XiaomiAuthError(f"Login failed with status {res.status_code}")
        if res.status_code != HTTPStatus.OK:
            raise XiaomiConnectionError(f"Login failed with status {res.status_code}")
        try:
            result = res.json()
        except ValueError as err:
            raise XiaomiConnectionError(
                "Failed to parse response from mi router"
            ) from err
        try:
            self.token = result["token"]
        except KeyError as err:
            raise XiaomiAuthError(
                f"Xiaomi login did not return a token, response was: {result}"
            ) from err

    def get_device_list(self) -> list[dict[str, Any]]:
        """Return the device list, refreshing the token once on auth failure."""
        if self.token is None:
            self.login()
        try:
            return self._retrieve_list()
        except XiaomiAuthError:
            _LOGGER.debug("Refreshing token and retrying device list refresh")
            self.login()
            return self._retrieve_list()

    def _retrieve_list(self) -> list[dict[str, Any]]:
        """Get the device list for the given host and token."""
        url = (
            f"http://{self.host}/cgi-bin/luci/;stok={self.token}"
            "/api/misystem/devicelist"
        )
        try:
            res = requests.get(url, timeout=LIST_TIMEOUT)
        except requests.exceptions.Timeout as err:
            raise XiaomiTimeoutError from err
        except requests.exceptions.ConnectionError as err:
            raise XiaomiConnectionError from err

        if res.status_code == HTTPStatus.UNAUTHORIZED:
            raise XiaomiAuthError(f"Device list failed with status {res.status_code}")
        if res.status_code != HTTPStatus.OK:
            raise XiaomiConnectionError(
                f"Device list failed with status {res.status_code}"
            )
        try:
            result = res.json()
        except ValueError as err:
            raise XiaomiConnectionError(
                "Failed to parse response from mi router"
            ) from err
        try:
            xiaomi_code = result["code"]
        except KeyError as err:
            raise XiaomiConnectionError(
                f"No field code in response from mi router: {result}"
            ) from err
        if xiaomi_code != 0:
            # A non-zero code means the stok (token) is rejected.
            raise XiaomiAuthError(
                f"Receive wrong Xiaomi code {xiaomi_code}, expected 0"
            )
        try:
            return result["list"]
        except KeyError as err:
            raise XiaomiConnectionError(
                f"No list in response from mi router: {result}"
            ) from err
