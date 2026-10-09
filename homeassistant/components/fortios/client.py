"""FortiOS library access shared by setup and polling."""

from dataclasses import dataclass
from typing import Any, override

from awesomeversion import AwesomeVersion
from fortiosapi import FortiOSAPI, NotLogged
from requests import Response
from requests.exceptions import RequestException

from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL

from .const import MINIMUM_VERSION


class UnsupportedVersion(Exception):
    """The device firmware is too old."""


@dataclass(frozen=True)
class FortiOSDevice:
    """A client reported by FortiOS."""

    mac: str
    hostname: str | None
    online: bool


class FortiOSAPIAdapter(FortiOSAPI):
    """Validate responses before the library reads their version fields."""

    @override
    def formatresponse(self, res: Response, vdom: str | None = None) -> dict[str, Any]:
        """Surface authentication and transport errors consistently."""
        if res.status_code in (401, 403):
            raise NotLogged
        res.raise_for_status()
        return FortiOSClient.check_response(super().formatresponse(res, vdom))

    def close(self) -> None:
        """Release the token-authenticated session without a logout request."""
        # fortiosapi exposes no public method to close a failed login session.
        self._session.close()  # pylint: disable=protected-access


class FortiOSClient:
    """Use the installed FortiOS library outside the event loop."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the library client."""
        self.api = FortiOSAPIAdapter()
        self.config = config
        self.serial: str = ""

    def connect(self) -> str:
        """Authenticate and validate the supported firmware version."""
        self.api.tokenlogin(
            self.config[CONF_HOST],
            self.config[CONF_TOKEN],
            self.config[CONF_VERIFY_SSL],
            None,
            12,
            "root",
        )
        status = self.check_response(self.api.monitor("system/status", ""))
        if AwesomeVersion(status["version"]) < AwesomeVersion(MINIMUM_VERSION):
            raise UnsupportedVersion
        self.serial = status["serial"]
        return self.serial

    def update(self) -> dict[str, FortiOSDevice]:
        """Read all clients with one monitoring request."""
        response = self.check_response(
            self.api.monitor(
                "user/device/query",
                "",
                parameters={"filter": "format=master_mac|hostname|is_online"},
            )
        )
        return {
            client["master_mac"].upper(): FortiOSDevice(
                client["master_mac"].upper(),
                client.get("hostname"),
                bool(client.get("is_online", False)),
            )
            for client in response["results"]
            if "master_mac" in client
        }

    @staticmethod
    def check_response(response: Any) -> dict[str, Any]:
        """Translate the library's HTTP error payloads."""
        if not isinstance(response, dict):
            raise RequestException("Invalid FortiOS response")
        if response.get("http_status") in (401, 403):
            raise NotLogged
        if response.get("status") == "error":
            raise RequestException("FortiOS request failed")
        return response

    def close(self) -> None:
        """Close the library session."""
        self.api.close()
