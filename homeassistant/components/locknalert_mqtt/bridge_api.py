"""HTTPS API client for LocknAlert bridge bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import DEFAULT_API_PORT

_LOGGER = logging.getLogger(__name__)


class LocknAlertApiError(Exception):
    """Base API error."""


class LocknAlertCannotConnect(LocknAlertApiError):
    """Bridge is unreachable."""


class LocknAlertInvalidAuth(LocknAlertApiError):
    """Bridge rejected credentials/token."""


class LocknAlertPairingRequired(LocknAlertApiError):
    """Bridge requires pairing mode/token."""


class LocknAlertInvalidResponse(LocknAlertApiError):
    """Bridge returned an invalid bootstrap payload."""


@dataclass(slots=True)
class LocknAlertBridgeApi:
    """Simple typed API wrapper for bridge onboarding."""

    host: str
    port: int = DEFAULT_API_PORT
    verify_ssl: bool = False

    @property
    def _base_url(self) -> str:
        return f"https://{self.host}:{self.port}"

    async def _request(
        self,
        session: ClientSession,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with session.request(
                method,
                url,
                json=json_data,
                ssl=self.verify_ssl,
                timeout=10,
            ) as resp:
                if resp.status in (401, 403):
                    raise LocknAlertInvalidAuth
                if resp.status == 409:
                    raise LocknAlertPairingRequired
                if resp.status >= 400:
                    raise LocknAlertCannotConnect(f"HTTP {resp.status}")
                data = await resp.json()
        except ClientError as err:
            raise LocknAlertCannotConnect from err
        if not isinstance(data, dict):
            raise LocknAlertInvalidResponse("Expected object")
        return data

    async def async_get_info(self, session: ClientSession) -> dict[str, Any]:
        """Fetch bridge identity and capabilities (expects bridge_serial)."""
        return await self._request(session, "GET", "/api/info")

    async def async_pair(
        self, session: ClientSession, pairing_token: str | None = None
    ) -> dict[str, Any]:
        """Pair with the bridge when required."""
        payload = {"token": pairing_token} if pairing_token else {}
        return await self._request(session, "POST", "/api/pair", json_data=payload)

    async def async_get_mqtt_bootstrap(self, session: ClientSession) -> dict[str, Any]:
        """Fetch LocknAlertLocknAlertMQTT host, credentials and topic prefix."""
        bootstrap = await self._request(session, "GET", "/api/mqtt/bootstrap")
        required = {"host", "port", "username", "password"}
        if not required.issubset(bootstrap):
            _LOGGER.debug("Invalid bootstrap payload: %s", bootstrap)
            raise LocknAlertInvalidResponse("Missing required LocknAlertLocknAlertMQTT fields")
        return bootstrap
