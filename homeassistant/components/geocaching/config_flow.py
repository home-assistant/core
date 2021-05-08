"""Config flow for Geocaching."""
from __future__ import annotations

import logging
from typing import Any

from geocachingapi.geocachingapi import GeocachingApi
from geocachingapi.models import GeocachingUser
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    # Geocaching is polling from the cloud
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    VERSION = 1
    data: Any = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        self.data = data
        api = GeocachingApi(
            token=data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        status = await api.update()
        existing_entry = await self.async_set_unique_id(
            f"{DOMAIN}_{status.user.username.lower()}"
        )
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await self._create_entry(status.user)

    async def _create_entry(self, user: GeocachingUser) -> FlowResult:
        return self.async_create_entry(title=user.username, data=self.data)
