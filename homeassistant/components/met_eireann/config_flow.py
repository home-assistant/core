"""Config flow to configure Met Éireann component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv

# pylint:disable=unused-import
from .const import DOMAIN, HOME_LOCATION_NAME


class MetEireannFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Check if an identical entity is already configured
            await self.async_set_unique_id(
                f"{user_input.get(CONF_LATITUDE)},{user_input.get(CONF_LONGITUDE)}"
            )
            self._abort_if_unique_id_configured()
        else:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                        vol.Required(
                            CONF_LATITUDE, default=self.hass.config.latitude
                        ): cv.latitude,
                        vol.Required(
                            CONF_LONGITUDE, default=self.hass.config.longitude
                        ): cv.longitude,
                        vol.Required(
                            CONF_ELEVATION, default=self.hass.config.elevation
                        ): int,
                    }
                ),
                errors=errors,
            )
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
