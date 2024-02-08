"""Config flow for microBees integration."""
from collections.abc import Mapping
import logging
from typing import Any

import microBeesPy

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for microBees."""

    VERSION = VERSION
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    reauth_entry: config_entries.ConfigEntry | None = None
    _title: str = ""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["read", "write"]
        return {"scope": " ".join(scopes)}

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""

        microbees = microBeesPy.microbees.MicroBees(
            session=aiohttp_client.async_get_clientsession(self.hass),
            token=data["token"]["access_token"],
        )

        current_user = await microbees.getMyProfile()
        if not self.reauth_entry:
            await self.async_set_unique_id(current_user.id)
        elif self.reauth_entry.unique_id == current_user.id:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        self._title = current_user.firstName + " " + current_user.lastName

        return self.async_create_entry(title=self._title, data=data)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
