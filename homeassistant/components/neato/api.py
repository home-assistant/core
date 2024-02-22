"""API for Neato Botvac bound to Home Assistant OAuth."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from typing import Any

import pybotvac

from homeassistant import config_entries, core
from homeassistant.components.application_credentials import AuthImplementation
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntryAuth(pybotvac.OAuthSession):  # type: ignore[misc]
    """Provide Neato Botvac authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize Neato Botvac Auth."""
        self.hass = hass
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(self.session.token, vendor=pybotvac.Neato())

    def refresh_tokens(self) -> str:
        """Refresh and return new Neato Botvac tokens."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token["access_token"]  # type: ignore[no-any-return]


class NeatoImplementation(AuthImplementation):
    """Neato implementation of LocalOAuth2Implementation.

    We need this class because we have to add client_secret
    and scope to the authorization request.
    """

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"client_secret": self.client_secret}

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize.

        We must make sure that the plus signs are not encoded.
        """
        url = await super().async_generate_authorize_url(flow_id)
        return f"{url}&scope=public_profile+control_robots+maps"
