"""Config flow for Waze Travel Time integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_AVOID_FERRIES,
    DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    DEFAULT_AVOID_TOLL_ROADS,
    DEFAULT_NAME,
    DEFAULT_REALTIME,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)
from .helpers import is_valid_config_entry

_LOGGER = logging.getLogger(__name__)


def is_dupe_import(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, user_input: dict[str, Any]
) -> bool:
    """Return whether imported config already exists."""
    entry_data = {**entry.data, **entry.options}
    defaults = {
        CONF_REALTIME: DEFAULT_REALTIME,
        CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
        CONF_UNITS: hass.config.units.name,
        CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
        CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
        CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
    }

    for key in (
        CONF_ORIGIN,
        CONF_DESTINATION,
        CONF_REGION,
        CONF_INCL_FILTER,
        CONF_EXCL_FILTER,
        CONF_REALTIME,
        CONF_VEHICLE_TYPE,
        CONF_UNITS,
        CONF_AVOID_FERRIES,
        CONF_AVOID_SUBSCRIPTION_ROADS,
        CONF_AVOID_TOLL_ROADS,
    ):
        # If the key is present the check is simple
        if key in user_input and user_input[key] != entry_data[key]:
            return False

        # If the key is not present, then we have to check if the key has a default and
        # if the default is in the options. If it doesn't have a default, we have to check
        # if the key is in the options
        if key not in user_input:
            if key in defaults and defaults[key] != entry_data[key]:
                return False

            if key not in defaults and key in entry_data:
                return False

    return True


class WazeOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Waze Travel Time."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize waze options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={k: v for k, v in user_input.items() if v not in (None, "")},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCL_FILTER,
                        default=self.config_entry.options.get(CONF_INCL_FILTER, ""),
                    ): cv.string,
                    vol.Optional(
                        CONF_EXCL_FILTER,
                        default=self.config_entry.options.get(CONF_EXCL_FILTER, ""),
                    ): cv.string,
                    vol.Optional(
                        CONF_REALTIME,
                        default=self.config_entry.options[CONF_REALTIME],
                    ): cv.boolean,
                    vol.Optional(
                        CONF_VEHICLE_TYPE,
                        default=self.config_entry.options[CONF_VEHICLE_TYPE],
                    ): vol.In(VEHICLE_TYPES),
                    vol.Optional(
                        CONF_UNITS,
                        default=self.config_entry.options[CONF_UNITS],
                    ): vol.In(UNITS),
                    vol.Optional(
                        CONF_AVOID_TOLL_ROADS,
                        default=self.config_entry.options[CONF_AVOID_TOLL_ROADS],
                    ): cv.boolean,
                    vol.Optional(
                        CONF_AVOID_SUBSCRIPTION_ROADS,
                        default=self.config_entry.options[
                            CONF_AVOID_SUBSCRIPTION_ROADS
                        ],
                    ): cv.boolean,
                    vol.Optional(
                        CONF_AVOID_FERRIES,
                        default=self.config_entry.options[CONF_AVOID_FERRIES],
                    ): cv.boolean,
                }
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waze Travel Time."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WazeOptionsFlow:
        """Get the options flow for this handler."""
        return WazeOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}

        if user_input:
            # We need to prevent duplicate imports
            if self.source == config_entries.SOURCE_IMPORT and any(
                is_dupe_import(self.hass, entry, user_input)
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.source == config_entries.SOURCE_IMPORT
            ):
                return self.async_abort(reason="already_configured")

            if (
                self.source == config_entries.SOURCE_IMPORT
                or await self.hass.async_add_executor_job(
                    is_valid_config_entry,
                    self.hass,
                    _LOGGER,
                    user_input[CONF_ORIGIN],
                    user_input[CONF_DESTINATION],
                    user_input[CONF_REGION],
                )
            ):
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                )

            # If we get here, it's because we couldn't connect
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): cv.string,
                    vol.Required(CONF_ORIGIN): cv.string,
                    vol.Required(CONF_DESTINATION): cv.string,
                    vol.Required(CONF_REGION): vol.In(REGIONS),
                }
            ),
            errors=errors,
        )

    async_step_import = async_step_user
