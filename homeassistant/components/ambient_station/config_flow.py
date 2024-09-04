"""Config flow to configure the Ambient PWS component."""

from __future__ import annotations

from typing import Any

from aioambient import API
from aioambient.errors import AmbientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import aiohttp_client

from .const import CONF_APP_KEY, DOMAIN


class AmbientStationFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an Ambient PWS config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
            {vol.Required(CONF_API_KEY): str, vol.Required(CONF_APP_KEY): str}
        )

    async def _show_form(self, errors: dict | None = None) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors if errors else {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        await self.async_set_unique_id(user_input[CONF_APP_KEY])
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)
        api = API(user_input[CONF_APP_KEY], user_input[CONF_API_KEY], session=session)

        try:
            devices = await api.get_devices()
        except AmbientError:
            return await self._show_form({"base": "invalid_key"})

        if not devices:
            return await self._show_form({"base": "no_devices"})

        # The Application Key (which identifies each config entry) is too long
        # to show nicely in the UI, so we take the first 12 characters (similar
        # to how GitHub does it):
        return self.async_create_entry(
            title=user_input[CONF_APP_KEY][:12], data=user_input
        )
