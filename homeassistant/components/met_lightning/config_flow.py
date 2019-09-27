"""Config flow to configure the Met lightning integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import callback

from .const import DEFAULT_RADIUS, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured Met lightning instances."""
    return set(
        "{0}, {1}".format(entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class MetLightningFlowHandler(config_entries.ConfigFlow):
    """Handle a Met lightning config flow."""

    VERSION = 1
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

        return self.async_create_entry(title=identifier, data=user_input)
