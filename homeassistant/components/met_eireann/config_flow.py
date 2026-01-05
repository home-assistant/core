"""Config flow to configure Met Éireann component."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, HOME_LOCATION_NAME


class MetEireannFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
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
            )
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
