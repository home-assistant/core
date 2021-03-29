"""Config flow for Waze Travel Time integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_REGION
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


class WazeOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Waze Travel Time."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
                        default=self.config_entry.options.get(
                            CONF_REALTIME, DEFAULT_REALTIME
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_VEHICLE_TYPE,
                        default=self.config_entry.options.get(
                            CONF_VEHICLE_TYPE, DEFAULT_VEHICLE_TYPE
                        ),
                    ): vol.In(VEHICLE_TYPES),
                    vol.Optional(
                        CONF_UNITS,
                        default=self.config_entry.options.get(
                            CONF_UNITS, self.hass.config.units.name
                        ),
                    ): vol.In(UNITS),
                    vol.Optional(
                        CONF_AVOID_TOLL_ROADS,
                        default=self.config_entry.options.get(
                            CONF_AVOID_TOLL_ROADS, DEFAULT_AVOID_TOLL_ROADS
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_AVOID_SUBSCRIPTION_ROADS,
                        default=self.config_entry.options.get(
                            CONF_AVOID_SUBSCRIPTION_ROADS,
                            DEFAULT_AVOID_SUBSCRIPTION_ROADS,
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_AVOID_FERRIES,
                        default=self.config_entry.options.get(
                            CONF_AVOID_FERRIES, DEFAULT_AVOID_FERRIES
                        ),
                    ): cv.boolean,
                }
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waze Travel Time."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WazeOptionsFlow:
        """Get the options flow for this handler."""
        return WazeOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(
                slugify(
                    f"{DOMAIN}_{user_input[CONF_ORIGIN]}_{user_input[CONF_DESTINATION]}"
                )
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=(
                    f"{DEFAULT_NAME}: {user_input[CONF_ORIGIN]} -> "
                    f"{user_input[CONF_DESTINATION]}"
                ),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORIGIN): cv.string,
                    vol.Required(CONF_DESTINATION): cv.string,
                    vol.Required(CONF_REGION): vol.In(REGIONS),
                }
            ),
        )

    async_step_import = async_step_user
