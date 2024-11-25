"""Config flow for Geocaching."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from geocachingapi.geocachingapi import GeocachingApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN, ENVIRONMENT


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    Geocaches = "Geocaches"
    Trackable = "Trackable"

    def __init__(self) -> None:
        """Initialize the flow handler."""
        super().__init__()
        self.data: dict[str, Any]
        self.title: str

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle OAuth response and redirect to additional configuration."""
        api = GeocachingApi(
            environment=ENVIRONMENT,
            token=data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        status = await api.update()
        if not status.user or not status.user.username:
            return self.async_abort(reason="oauth_error")

        if existing_entry := await self.async_set_unique_id(
            status.user.username.lower()
        ):
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        self.data = data
        self.title = status.user.username
        # Create the final config entry
        return await self.async_step_additional_config(None)

    async def async_step_additional_config(
        self,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Handle additional user input after authentication."""
        if user_input is None:
            # Show the form to collect additional input
            return self.async_show_form(
                step_id="additional_config",
                data_schema=vol.Schema(
                    {
                        vol.Optional(self.Geocaches): str,
                        vol.Optional(self.Trackable): str,
                    }
                ),
            )

        # Check if user has entered anything
        if user_input.get(self.Geocaches):
            self.data[self.Geocaches] = user_input[self.Geocaches]

        if user_input.get(self.Trackable):
            self.data[self.Trackable] = user_input[self.Trackable]

        return self.async_create_entry(title=self.title, data=self.data)
