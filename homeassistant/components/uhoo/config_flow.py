"""Imports for config_flow.py."""

from typing import Any

from uhooapi import Client
from uhooapi.errors import UnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class UhooFlowHandler(ConfigFlow, domain=DOMAIN):
    """Setup Uhoo flow handlers."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        self._errors = {}

        if user_input is None:
            return await self._show_config_form(user_input)

        # Set the unique ID for the config flow.
        api_key = user_input[CONF_API_KEY]
        if not api_key:
            self._errors["base"] = "auth"
            return await self._show_config_form(user_input)

        await self.async_set_unique_id(api_key)
        self._abort_if_unique_id_configured()

        valid = await self._test_credentials(api_key)
        if not valid:
            self._errors["base"] = "auth"
            return await self._show_config_form(user_input)

        entry_num = len(self._async_current_entries()) + 1
        return self.async_create_entry(title=f"Account {entry_num}", data=user_input)

    async def _show_config_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            user_input = {}
            user_input[CONF_API_KEY] = ""
            return await self._show_config_form(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA, user_input or {}
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, api_key):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            client = Client(api_key, session, debug=True)
            await client.login()
        except UnauthorizedError as err:
            LOGGER.error(
                f"Error: received a 401 Unauthorized error attempting to login:\n{err}"
            )
            return False
        else:
            return True
