"""Config flow to configure the Sensor.Community integration."""

from __future__ import annotations

from typing import Any

from luftdaten import Luftdaten
from luftdaten.exceptions import LuftdatenConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_SENSOR_ID, DOMAIN


class SensorCommunityFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Sensor.Community config flow."""

    VERSION = 1

    @callback
    def _show_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SENSOR_ID): cv.positive_int,
                    vol.Optional(CONF_SHOW_ON_MAP, default=False): bool,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self._show_form()

        await self.async_set_unique_id(str(user_input[CONF_SENSOR_ID]))
        self._abort_if_unique_id_configured()

        sensor_community = Luftdaten(user_input[CONF_SENSOR_ID])
        try:
            await sensor_community.get_data()
            valid = await sensor_community.validate_sensor()
        except LuftdatenConnectionError:
            return self._show_form({CONF_SENSOR_ID: "cannot_connect"})

        if not valid:
            return self._show_form({CONF_SENSOR_ID: "invalid_sensor"})

        return self.async_create_entry(
            title=str(user_input[CONF_SENSOR_ID]), data=user_input
        )
