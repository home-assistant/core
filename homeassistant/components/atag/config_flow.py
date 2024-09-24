"""Config flow for the Atag component."""

from typing import Any

import pyatag
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=pyatag.const.DEFAULT_PORT): vol.Coerce(int),
}


class AtagConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Atag."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if not user_input:
            return await self._show_form()

        atag = pyatag.AtagOne(session=async_get_clientsession(self.hass), **user_input)
        try:
            await atag.update()

        except pyatag.Unauthorized:
            return await self._show_form({"base": "unauthorized"})
        except pyatag.AtagException:
            return await self._show_form({"base": "cannot_connect"})

        await self.async_set_unique_id(atag.id)
        self._abort_if_unique_id_configured(updates=user_input)

        return self.async_create_entry(title=atag.id, data=user_input)

    async def _show_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )
