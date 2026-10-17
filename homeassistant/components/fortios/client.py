"""Asynchronous library access shared by FortiOS setup and polling."""

from dataclasses import dataclass
from typing import Any

from aiofortiosapi import (
    FortiOSAuthenticationError,
    FortiOSClient as FortiOSAPI,
    FortiOSResponseError,
    SystemStatus,
)
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionException
from yarl import URL

from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import MINIMUM_VERSION


class UnsupportedVersion(Exception):
    """The device firmware is too old."""


@dataclass(frozen=True)
class FortiOSDevice:
    """A client reported by FortiOS."""

    mac: str
    hostname: str | None
    online: bool


class FortiOSClient:
    """Use the maintained library with Home Assistant's shared session."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize without owning or closing the shared HTTP session."""
        try:
            url = URL(f"https://{config[CONF_HOST]}")
            host = url.raw_host
            port = url.port
        except ValueError as err:
            raise FortiOSResponseError("Invalid FortiOS host") from err
        if (
            not host
            or url.user
            or url.password
            or url.path != "/"
            or url.query
            or url.fragment
        ):
            raise FortiOSResponseError("Invalid FortiOS host")
        self.api = FortiOSAPI(
            f"[{host}]" if ":" in host else host,
            config[CONF_TOKEN],
            session=async_get_clientsession(hass),
            port=port or 443,
            verify_ssl=config[CONF_VERIFY_SSL],
            vdom="root",
            request_timeout=12,
        )
        self.serial = ""

    async def connect(self) -> str:
        """Authenticate and validate device identity and firmware."""
        response = self.check_response(
            await self.api.get("api/v2/monitor/system/status")
        )
        status = SystemStatus.from_api(response)
        if not status.serial or not status.version:
            raise FortiOSResponseError("Missing FortiOS device identity or version")
        try:
            supported = AwesomeVersion(status.version) >= AwesomeVersion(
                MINIMUM_VERSION
            )
        except AwesomeVersionException as err:
            raise FortiOSResponseError("Invalid FortiOS firmware version") from err
        if not supported:
            raise UnsupportedVersion
        self.serial = status.serial
        return self.serial

    async def update(self) -> dict[str, FortiOSDevice]:
        """Read all clients using the legacy master-MAC query format."""
        response = self.check_response(
            await self.api.get(
                "api/v2/monitor/user/device/query",
                params={"filter": "format=master_mac|hostname|is_online"},
            )
        )
        if not isinstance(clients := response.get("results"), list):
            raise FortiOSResponseError("Invalid FortiOS device list")
        devices = {}
        for client in clients:
            if not isinstance(client, dict):
                raise FortiOSResponseError("Invalid FortiOS device")
            if not isinstance(mac := client.get("master_mac"), str) or not mac:
                continue
            mac = mac.upper()
            hostname = client.get("hostname")
            devices[mac] = FortiOSDevice(
                mac,
                hostname if isinstance(hostname, str) else None,
                bool(client.get("is_online", False)),
            )
        return devices

    @staticmethod
    def check_response(response: Any) -> dict[str, Any]:
        """Reject malformed or failed envelopes before parsing their data."""
        if isinstance(response, dict) and response.get("http_status") in (401, 403):
            raise FortiOSAuthenticationError("FortiOS authentication failed")
        if not isinstance(response, dict) or response.get("status") == "error":
            raise FortiOSResponseError("Invalid FortiOS response")
        return response
