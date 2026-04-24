"""OAuth2 implementation for Hisense AC Plugin."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from connectlife_cloud import CLIENT_ID, CLIENT_SECRET, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AUTH_CALLBACK_PATH

from .const import DOMAIN, HA_HOST

_LOGGER = logging.getLogger(__name__)


class HisenseOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Hisense OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize Hisense OAuth2 implementation."""
        super().__init__(
            hass=hass,
            domain=DOMAIN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )
        _LOGGER.debug(
            "Initialized OAuth2 implementation with authorize_url: %s, token_url: %s",
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Hisense AC"

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{HA_HOST}{AUTH_CALLBACK_PATH}"

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        _LOGGER.debug(
            "Resolving external data: %s",
            {
                k: "***" if k in ("code", "state") else v
                for k, v in (
                    external_data if isinstance(external_data, dict) else {}
                ).items()
            },
        )
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }
        return await self._token_request(data)

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        _LOGGER.debug("Refreshing token")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token["refresh_token"],
        }
        new_token = await self._token_request(data)
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""

        session = async_get_clientsession(self.hass)
        data["client_id"] = self.client_id
        data["client_secret"] = self.client_secret
        data["redirect_uri"] = f"{HA_HOST}{AUTH_CALLBACK_PATH}"

        resp = await session.post(self.token_url, data=data)
        resp.raise_for_status()
        resp_json = cast(dict, await resp.json())

        # Add expires_at to the token response
        if "expires_in" in resp_json and "expires_at" not in resp_json:
            resp_json["expires_at"] = time.time() + resp_json["expires_in"]

        return resp_json
