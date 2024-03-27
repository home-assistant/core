"""Config flow for epson integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from . import validate_projector
from .const import DOMAIN
from .exceptions import CannotConnect, PoweredOff

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_NAME, default=DOMAIN): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class EpsonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for epson."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                projector = await validate_projector(
                    hass=self.hass,
                    host=user_input[CONF_HOST],
                    check_power=True,
                    check_powered_on=True,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except PoweredOff:
                _LOGGER.warning(
                    "You need to turn ON projector for initial configuration"
                )
                errors["base"] = "powered_off"
            else:
                serial_no = await projector.get_serial_number()
                await self.async_set_unique_id(serial_no)
                self._abort_if_unique_id_configured()
                user_input.pop(CONF_PORT, None)
                return self.async_create_entry(
                    title=user_input.pop(CONF_NAME), data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
