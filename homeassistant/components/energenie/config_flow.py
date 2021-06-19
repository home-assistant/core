"""Config flow for Energenie integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from gpiozero import exc

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Energenie Socket"): str,
        vol.Required("socket_number", default=1): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for energenie."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self._async_abort_entries_match({"socket_number": user_input["socket_number"]})
                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )
            except exc.BadPinFactory:
                _LOGGER.exception("Socket number is not in range from 1-4.")
                errors["base"] = "invalid_range"
            except exc.EnergenieBadSocket:
                _LOGGER.exception("Pimote addon could not be located.")
                errors["base"] = "pimote_not_found"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

