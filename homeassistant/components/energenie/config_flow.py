"""Config flow for Energenie integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import HomeAssistantError

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

    async def in_range(self, socket_number):
        """Verify that input is between the range of 1 and 4."""
        if 1 <= socket_number <= 4:
            return True
        raise InvalidRange

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await self.in_range(user_input["socket_number"])
                await self.async_set_unique_id(f'energenie-socket-{user_input["socket_number"]}')
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )
            except InvalidRange:
                _LOGGER.exception("Socket number is not in range from 1-4")
                errors["base"] = "invalid_range"
            except:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidRange(HomeAssistantError):
    """Socket Number doesn't match criteria."""
