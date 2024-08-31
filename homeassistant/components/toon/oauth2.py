"""OAuth2 implementations for Toon."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import config_flow


def register_oauth2_implementations(
    hass: HomeAssistant, client_id: str, client_secret: str
) -> None:
    """Register Toon OAuth2 implementations."""
    config_flow.ToonFlowHandler.async_register_implementation(
        hass,
        ToonLocalOAuth2Implementation(
            hass,
            client_id=client_id,
            client_secret=client_secret,
            name="Eneco Toon",
            tenant_id="eneco",
            issuer="identity.toon.eu",
        ),
    )
    config_flow.ToonFlowHandler.async_register_implementation(
        hass,
        ToonLocalOAuth2Implementation(
            hass,
            client_id=client_id,
            client_secret=client_secret,
            name="Engie Electrabel Boxx",
            tenant_id="electrabel",
            issuer="identity.toon.eu",
        ),
    )
    config_flow.ToonFlowHandler.async_register_implementation(
        hass,
        ToonLocalOAuth2Implementation(
            hass,
            client_id=client_id,
            client_secret=client_secret,
            name="Viesgo",
            tenant_id="viesgo",
        ),
    )


class ToonLocalOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Local OAuth2 implementation for Toon."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        name: str,
        tenant_id: str,
        issuer: str | None = None,
    ) -> None:
        """Local Toon Oauth Implementation."""
        self._name = name
        self.tenant_id = tenant_id
        self.issuer = issuer

        super().__init__(
            hass=hass,
            domain=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://api.toon.eu/authorize",
            token_url="https://api.toon.eu/token",
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return f"{self._name} via Configuration.yaml"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        data = {"tenant_id": self.tenant_id}

        if self.issuer is not None:
            data["issuer"] = self.issuer

        return data

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Initialize local Toon auth implementation."""
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
            "tenant_id": self.tenant_id,
        }

        if self.issuer is not None:
            data["issuer"] = self.issuer

        return await self._token_request(data)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": token["refresh_token"],
            "tenant_id": self.tenant_id,
        }

        new_token = await self._token_request(data)
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)
        headers = {}

        data["client_id"] = self.client_id
        data["tenant_id"] = self.tenant_id

        if self.client_secret is not None:
            data["client_secret"] = self.client_secret

        if self.issuer is not None:
            data["issuer"] = self.issuer
            headers["issuer"] = self.issuer

        resp = await session.post(self.token_url, data=data, headers=headers)
        resp.raise_for_status()
        resp_json = cast(dict, await resp.json())
        # The Toon API returns "expires_in" as a string for some tenants.
        # This is not according to OAuth specifications.
        resp_json["expires_in"] = float(resp_json["expires_in"])
        return resp_json
