"""Provide oauth implementations for the Teslemetry integration."""

import asyncio
from typing import Any, Final, override

from tesla_fleet_api.teslemetry import register_client

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORIZE_URL, DCR_AUTH_DOMAIN, DOMAIN, SOFTWARE_ID, TOKEN_URL

REGISTRATION_LOCK: Final = f"{DOMAIN}_registration_lock"


class TeslemetryImplementation(
    config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce
):
    """Teslemetry OAuth2 implementation."""

    def __init__(self, hass: HomeAssistant, domain: str, client_id: str) -> None:
        """Initialize OAuth2 implementation."""

        super().__init__(
            hass,
            domain,
            client_id,
            AUTHORIZE_URL,
            TOKEN_URL,
        )

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "Teslemetry OAuth2"

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        data: dict = {
            "name": self.hass.config.location_name,
        }
        data.update(super().extra_authorize_data)
        return data

    @property
    @override
    def extra_token_resolve_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token resolve request."""
        data: dict = {
            "name": self.hass.config.location_name,
            "software_id": SOFTWARE_ID,
            "software_version": __version__,
        }
        data.update(super().extra_token_resolve_data)
        return data

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        # Re-send software metadata so the server picks up a version change after an upgrade.
        new_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
                "software_id": SOFTWARE_ID,
                "software_version": __version__,
            }
        )

        # Merging a response without one would keep the stale access token while
        # extending its expiry, so the session would never recover.
        if not new_token.get("access_token"):
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)

        return {**token, **new_token}


async def async_ensure_client_credential(hass: HomeAssistant) -> None:
    """Register an OAuth client for this installation if one does not exist yet."""
    # Serialize and re-check inside the lock so two concurrent recoveries cannot
    # register and persist different clients under the same auth key.
    lock: asyncio.Lock = hass.data.setdefault(REGISTRATION_LOCK, asyncio.Lock())
    async with lock:
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            hass, DOMAIN
        )
        if DCR_AUTH_DOMAIN in implementations:
            return

        registration = await register_client(
            async_get_clientsession(hass),
            "Home Assistant",
            SOFTWARE_ID,
            __version__,
        )
        # Import under a dedicated auth_domain so the dynamically registered
        # client never shares an auth key with the legacy static client that
        # backs migrated v1 entries; otherwise a later legacy migration would
        # overwrite this credential and the DCR-backed entry would resolve to
        # the wrong client.
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(registration.client_id, "", name="Teslemetry"),
            auth_domain=DCR_AUTH_DOMAIN,
        )
