"""Config flow to configure the WWLLN integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (  # pylint: disable=unused-import
    CONF_WINDOW,
    DEFAULT_RADIUS,
    DEFAULT_WINDOW,
    DOMAIN,
)


class WWLLNFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WWLLN config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def data_schema(self):
        """Return the data schema for the user form."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors or {}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return WWLLNOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=identifier,
            data={
                CONF_LATITUDE: user_input[CONF_LATITUDE],
                CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                CONF_RADIUS: DEFAULT_RADIUS,
                CONF_WINDOW: DEFAULT_WINDOW,
            },
        )


class WWLLNOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a WWLLN options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RADIUS, default=self.config_entry.options.get(CONF_RADIUS),
                    ): int,
                    vol.Optional(
                        CONF_WINDOW, default=self.config_entry.options.get(CONF_WINDOW),
                    ): int,
                }
            ),
        )
