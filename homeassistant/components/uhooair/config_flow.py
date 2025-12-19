"""Imports for config_flow.py."""

from typing import Any

from uhooapi import Client
from uhooapi.errors import UnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class UhooFlowHandler(ConfigFlow, domain=DOMAIN):
    """Setup Uhoo flow handlers."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,  # This makes it a censored password field
                        autocomplete="current-password",  # Helps browser password managers
                    )
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        self._errors = {}
        # Check if an entry already exists
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Set the unique ID for the config flow.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            user_input = {}
            user_input[CONF_API_KEY] = ""
            return await self._show_config_form(user_input)

        valid = await self._test_credentials(user_input[CONF_API_KEY])
        if not valid:
            self._errors["base"] = "auth"
            return await self._show_config_form(user_input)
        return self.async_create_entry(title="uHoo Devices", data=user_input)

    async def _show_config_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            user_input = {}
            user_input[CONF_API_KEY] = ""
            return await self._show_config_form(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input[CONF_API_KEY]
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,  # This makes it a censored password field
                            autocomplete="current-password",  # Helps browser password managers
                        )
                    ),
                }
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
