"""Config flow for the Velbus platform."""
from __future__ import annotations

import velbusaio
from velbusaio.exceptions import VelbusConnectionFailed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def velbus_entries(hass: HomeAssistant):
    """Return connections for Velbus domain."""
    return {
        (entry.data[CONF_PORT]) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class VelbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._errors: dict[str, str] = {}

    def _create_device(self, name: str, prt: str):
        """Create an entry async."""
        return self.async_create_entry(title=name, data={CONF_PORT: prt})

    async def _test_connection(self, prt):
        """Try to connect to the velbus with the port specified."""
        try:
            controller = velbusaio.controller.Velbus(prt)
            await controller.connect(True)
            await controller.stop()
        except VelbusConnectionFailed:
            self._errors[CONF_PORT] = "cannot_connect"
            return False
        return True

    def _prt_in_configuration_exists(self, prt: str) -> bool:
        """Return True if port exists in configuration."""
        if prt in velbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            prt = user_input[CONF_PORT]
            if not self._prt_in_configuration_exists(prt):
                if await self._test_connection(prt):
                    return self._create_device(name, prt)
            else:
                self._errors[CONF_PORT] = "already_configured"
        else:
            user_input = {}
            user_input[CONF_NAME] = ""
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        user_input[CONF_NAME] = "Velbus Import"
        prt = user_input[CONF_PORT]
        if self._prt_in_configuration_exists(prt):
            # if the velbus import is already in the config
            # we should not proceed the import
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)
