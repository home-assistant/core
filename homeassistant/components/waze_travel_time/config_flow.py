"""Config flow for Waze Travel Time integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_REGION
from homeassistant.util import slugify

from .const import (  # pylint:disable=unused-import
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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waze Travel Time."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
                title=user_input.get(CONF_NAME, DEFAULT_NAME), data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORIGIN): str,
                    vol.Required(CONF_DESTINATION): str,
                    vol.Required(CONF_REGION): vol.In(REGIONS),
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_UNITS): vol.In(UNITS),
                    vol.Optional(
                        CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE
                    ): vol.In(VEHICLE_TYPES),
                    vol.Optional(CONF_INCL_FILTER): str,
                    vol.Optional(CONF_EXCL_FILTER): str,
                    vol.Optional(CONF_REALTIME, default=DEFAULT_REALTIME): bool,
                    vol.Optional(
                        CONF_AVOID_TOLL_ROADS, default=DEFAULT_AVOID_TOLL_ROADS
                    ): bool,
                    vol.Optional(
                        CONF_AVOID_SUBSCRIPTION_ROADS,
                        default=DEFAULT_AVOID_SUBSCRIPTION_ROADS,
                    ): bool,
                    vol.Optional(
                        CONF_AVOID_FERRIES, default=DEFAULT_AVOID_FERRIES
                    ): bool,
                }
            ),
        )
