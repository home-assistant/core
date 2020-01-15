"""Config flow to configure the WWLLN integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_WINDOW, DEFAULT_RADIUS, DEFAULT_WINDOW, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured WWLLN instances."""
    return set(
        "{0}, {1}".format(entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class WWLLNFlowHandler(config_entries.ConfigFlow):
    """Handle a WWLLN config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        identifier = "{0}, {1}".format(
            user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
        )
        if identifier in configured_instances(self.hass):
            return await self._show_form({"base": "identifier_exists"})

        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            user_input[CONF_UNIT_SYSTEM] = CONF_UNIT_SYSTEM_IMPERIAL
        else:
            user_input[CONF_UNIT_SYSTEM] = CONF_UNIT_SYSTEM_METRIC

        # When importing from `configuration.yaml`, we give the user
        # flexibility by allowing the `window` parameter to be any type
        # of time period. This will always return a timedelta; unfortunately,
        # timedeltas aren't JSON-serializable, so we can't store them in a
        # config entry as-is; instead, we save the total seconds as an int:
        if CONF_WINDOW in user_input:
            user_input[CONF_WINDOW] = user_input[CONF_WINDOW].total_seconds()
        else:
            user_input[CONF_WINDOW] = DEFAULT_WINDOW.total_seconds()

        return self.async_create_entry(title=identifier, data=user_input)
