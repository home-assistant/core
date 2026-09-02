"""Config flow for the Sky Hub integration."""

from typing import Any, override

import aiohttp
from pyskyqhub.skyq_hub import SkyQHub
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST, default=DEFAULT_HOST): str})


class SkyHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sky Hub."""

    VERSION = 1

    async def _async_can_connect(self, host: str) -> bool:
        """Return True if the Sky Hub at host returns data."""
        hub = SkyQHub(async_get_clientsession(self.hass), host)
        try:
            return await hub.async_get_skyhub_data() is not None
        except aiohttp.ClientError, TimeoutError:
            return False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if await self._async_can_connect(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import existing configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        if await self._async_can_connect(import_data[CONF_HOST]):
            return self.async_create_entry(
                title=import_data[CONF_HOST], data=import_data
            )
        return self.async_abort(reason="cannot_connect")
