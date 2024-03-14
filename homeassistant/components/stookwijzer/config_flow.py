"""Config flow to configure the Stookwijzer integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN


class StookwijzerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Stookwijzer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            return self.async_create_entry(
                title="Stookwijzer",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default={
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ): LocationSelector()
                }
            ),
        )
