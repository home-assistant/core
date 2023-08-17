"""Config flow to configure IPMA component."""
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


class IpmaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for IPMA component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LATITUDE): cv.latitude,
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                    }
                ),
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                },
            ),
        )
