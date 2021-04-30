"""Config flow for Waze Travel Time integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_REGION
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

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
    DEFAULT_NAME,
    DOMAIN,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)
from .helpers import is_valid_config_entry

_LOGGER = logging.getLogger(__name__)


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
            await self.async_set_unique_id(
                slugify(
                    f"{DOMAIN}_{user_input[CONF_ORIGIN]}_{user_input[CONF_DESTINATION]}"
                )
            )
            self._abort_if_unique_id_configured()
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
