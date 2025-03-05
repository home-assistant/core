"""Config flow for Geocaching."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from geocachingapi.geocachingapi import GeocachingApi
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import TextSelector, TextSelectorType

from .const import (
    CACHES_SINGLE_TITLE,
    CONFIG_FLOW_GEOCACHES_SECTION_ID,
    DOMAIN,
    ENVIRONMENT,
    MAX_TRACKED_CACHES,
)


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    data: dict[str, Any] = {}
    title: str = "Geocaching"

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

        # Create the final config entry
        self.data = data
        return await self.async_step_additional_config(None)

    async def async_step_additional_config(
        self,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Handle additional user input after authentication."""

        # Returns a schema for entering a list of strings
        def string_list_schema(single_entry_title: str) -> vol.Schema:
            return vol.Schema(
                {
                    single_entry_title: TextSelector(
                        {"multiple": True, "type": TextSelectorType.TEXT}
                    )
                }
            )

        if user_input is None:
            # Show the form to collect additional input
            return self.async_show_form(
                step_id="additional_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONFIG_FLOW_GEOCACHES_SECTION_ID
                        ): data_entry_flow.section(
                            string_list_schema(CACHES_SINGLE_TITLE),
                            {"collapsed": False},
                        ),
                    }
                ),
            )

        def get_or_default(path: list[str], default: Any) -> Any:
            """Get a value from a nested dictionary or return a default value."""
            if len(path) < 1:
                raise ValueError("Path must contain at least one key")

            value = user_input
            for key in path:
                if key not in value:
                    return default
                value = value[key]
            return value

        # Store the provided tracked caches
        self.data[CONFIG_FLOW_GEOCACHES_SECTION_ID] = get_or_default(
            [CONFIG_FLOW_GEOCACHES_SECTION_ID, CACHES_SINGLE_TITLE], []
        )
        if len(self.data[CONFIG_FLOW_GEOCACHES_SECTION_ID]) > MAX_TRACKED_CACHES:
            raise ValueError(f"Cannot track more than {MAX_TRACKED_CACHES} caches")

        return self.async_create_entry(title=self.title, data=self.data)
