"""Config flow to configure the Stookwijzer integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


class StookwijzerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Stookwijzer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                }
            ),
        )
