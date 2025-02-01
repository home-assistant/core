"""Config flow for epson integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import validate_projector
from .const import CONF_CONNECTION_TYPE, DOMAIN, HTTP, SERIAL
from .exceptions import CannotConnect, PoweredOff

ALLOWED_CONNECTION_TYPE = [HTTP, SERIAL]

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=HTTP): SelectSelector(
            SelectSelectorConfig(
                options=ALLOWED_CONNECTION_TYPE, translation_key="connection_type"
            )
        ),
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_NAME, default=DOMAIN): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class EpsonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for epson."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Epson projector doesn't appear to need to be on for serial
            check_power = user_input[CONF_CONNECTION_TYPE] != SERIAL
            projector = None
            try:
                projector = await validate_projector(
                    hass=self.hass,
                    conn_type=user_input[CONF_CONNECTION_TYPE],
                    host=user_input[CONF_HOST],
                    check_power=True,
                    check_powered_on=check_power,
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
            finally:
                if projector:
                    projector.close()
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
