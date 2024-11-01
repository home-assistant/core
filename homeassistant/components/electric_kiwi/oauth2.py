"""OAuth2 implementations for Toon."""

from __future__ import annotations

import base64
from typing import Any, cast

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import SCOPE_VALUES


class ElectricKiwiLocalOAuth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Electric Kiwi."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Set up Electric Kiwi oauth."""
        super().__init__(
            hass=hass,
            auth_domain=domain,
            credential=client_credential,
            authorization_server=authorization_server,
        )

        self._name = client_credential.name

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPE_VALUES}

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Initialize local Electric Kiwi auth implementation."""
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }

        return await self._token_request(data)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }

        new_token = await self._token_request(data)
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)
        client_str = f"{self.client_id}:{self.client_secret}"
        client_string_bytes = client_str.encode("ascii")

        base64_bytes = base64.b64encode(client_string_bytes)
        base64_client = base64_bytes.decode("ascii")
        headers = {"Authorization": f"Basic {base64_client}"}

        resp = await session.post(self.token_url, data=data, headers=headers)
        resp.raise_for_status()
        return cast(dict, await resp.json())
