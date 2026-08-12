"""Provide oauth implementations for the Teslemetry integration."""

import asyncio
from typing import Any, Final, override

from aiohttp import ClientError

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORIZE_URL, DOMAIN, REGISTER_URL, SOFTWARE_ID, TOKEN_URL

REGISTRATION_LOCK: Final = f"{DOMAIN}_registration_lock"


class TeslemetryRegistrationError(Exception):
    """Raised when dynamic client registration cannot be completed.

    Internal control-flow signal: always caught and converted into a deferred
    startup retry or an in-place ``cannot_connect`` config-flow step, so it is
    never surfaced to the user directly.
    """


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
        """Refresh a token.

        Software metadata is re-sent on every refresh so the server can pick
        up a software_version change after a Home Assistant upgrade.
        """
        new_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
                "software_id": SOFTWARE_ID,
                "software_version": __version__,
            }
        )

        return {**token, **new_token}


async def async_ensure_client_credential(hass: HomeAssistant) -> None:
    """Ensure an OAuth client is registered for this Home Assistant installation.

    Teslemetry supports RFC 7591 dynamic client registration. The first time
    this installation connects, a client is registered and its client_id is
    imported as the application credential used for every future
    authorization, including reauthentication, so the server can recognize
    repeat authorizations as the same client instead of minting a new one.

    Registration is serialized with a per-installation lock and re-checked
    inside it so two concurrent flows recovering from a setup-time failure
    cannot register and persist different clients under the same auth key.
    """
    lock: asyncio.Lock = hass.data.setdefault(REGISTRATION_LOCK, asyncio.Lock())
    async with lock:
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            hass, DOMAIN
        )
        if DOMAIN in implementations:
            return

        session = async_get_clientsession(hass)
        try:
            response = await session.post(
                REGISTER_URL,
                json={
                    "client_name": "Home Assistant",
                    "software_id": SOFTWARE_ID,
                    "software_version": __version__,
                },
            )
            response.raise_for_status()
            registration = await response.json()
        except (ClientError, TimeoutError) as err:
            raise TeslemetryRegistrationError(
                "Could not reach Teslemetry to register a client"
            ) from err
        except ValueError as err:
            raise TeslemetryRegistrationError(
                "Teslemetry returned a malformed registration response"
            ) from err

        client_id = registration.get("client_id") if registration else None
        if not client_id or not isinstance(client_id, str):
            raise TeslemetryRegistrationError(
                "Teslemetry registration response did not contain a client_id"
            )

        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(client_id, "", name="Teslemetry"),
        )
