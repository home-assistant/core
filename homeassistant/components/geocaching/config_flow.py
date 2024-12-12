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
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorMode,
    TextSelector,
    TextSelectorType,
)

from .const import (
    CACHES_SINGLE_TITLE,
    CONFIG_FLOW_GEOCACHES_SECTION_ID,
    CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID,
    CONFIG_FLOW_TRACKABLES_SECTION_ID,
    DOMAIN,
    ENVIRONMENT,
    NEARBY_CACHES_COUNT_TITLE,
    NEARBY_CACHES_RADIUS_TITLE,
    TRACKABLES_SINGLE_TITLE,
    USE_TEST_CONFIG,
)


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

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

        # Returns a schema for entering a list of strings
        def string_list_schema(single_entry_title: str) -> vol.Schema:
            return vol.Schema(
                {
                    single_entry_title: TextSelector(
                        {"multiple": True, "type": TextSelectorType.TEXT}
                    )
                }
            )

        # TODO: Remove this temporary override, only used during development | pylint: disable=fixme
        if USE_TEST_CONFIG:
            user_input = {}

        if user_input is None:
            # Show the form to collect additional input
            return self.async_show_form(
                step_id="additional_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID
                        ): data_entry_flow.section(
                            vol.Schema(
                                {
                                    vol.Required(
                                        NEARBY_CACHES_COUNT_TITLE
                                    ): NumberSelector(
                                        {
                                            "min": 0,
                                            "max": 50,
                                            "step": 1,
                                            "unit_of_measurement": "count",
                                            "mode": NumberSelectorMode.SLIDER,
                                        }
                                    ),
                                    vol.Required(
                                        NEARBY_CACHES_RADIUS_TITLE
                                    ): NumberSelector(
                                        {
                                            "min": 0.1,
                                            "step": 0.001,
                                            "unit_of_measurement": "km",
                                            "mode": NumberSelectorMode.BOX,
                                        }
                                    ),
                                }
                            ),
                            {"collapsed": False},
                        ),
                        vol.Required(
                            CONFIG_FLOW_GEOCACHES_SECTION_ID
                        ): data_entry_flow.section(
                            string_list_schema(CACHES_SINGLE_TITLE),
                            {"collapsed": False},
                        ),
                        vol.Required(
                            CONFIG_FLOW_TRACKABLES_SECTION_ID
                        ): data_entry_flow.section(
                            string_list_schema(TRACKABLES_SINGLE_TITLE),
                            {"collapsed": False},
                        ),
                    }
                ),
            )

        # Store the provided nearby caches count
        self.data[NEARBY_CACHES_COUNT_TITLE] = (
            user_input[CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID][
                NEARBY_CACHES_COUNT_TITLE
            ]
            if user_input.get(CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID)
            else 0
        )

        # Store the provided nearby caches radius
        self.data[NEARBY_CACHES_RADIUS_TITLE] = (
            user_input[CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID][
                NEARBY_CACHES_RADIUS_TITLE
            ]
            if user_input.get(CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID)
            else 1
        )

        # Store the provided tracked caches
        self.data[CONFIG_FLOW_GEOCACHES_SECTION_ID] = (
            user_input[CONFIG_FLOW_GEOCACHES_SECTION_ID][CACHES_SINGLE_TITLE]
            if user_input.get(CONFIG_FLOW_GEOCACHES_SECTION_ID)
            else []
        )

        # Store the provided tracked trackables
        self.data[CONFIG_FLOW_TRACKABLES_SECTION_ID] = (
            user_input[CONFIG_FLOW_TRACKABLES_SECTION_ID][TRACKABLES_SINGLE_TITLE]
            if user_input.get(CONFIG_FLOW_TRACKABLES_SECTION_ID)
            else []
        )

        return self.async_create_entry(title=self.title, data=self.data)
