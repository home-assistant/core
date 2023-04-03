"""Config flow to configure the Swisscom integration."""
from __future__ import annotations

import logging
from sc_inetbox_adapter import DEFAULT_HOST, DEFAULT_PROTOCOL
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
)

from .const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_NAME,
    DOMAIN,
)

from .errors import CannotLoginException
from .router import get_api

_LOGGER = logging.getLogger(__name__)

def _user_schema_with_defaults(user_input):
    user_schema = {vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str}
    user_schema.update(_ordered_shared_schema(user_input))

    return vol.Schema(user_schema)

def _ordered_shared_schema(schema_input):
    return {
        vol.Required(CONF_PASSWORD, default=schema_input.get(CONF_PASSWORD, "")): str,
    }

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
                    ),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=settings_schema)

class InternetBoxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the internetbox config flow."""
        self.placeholders = {
            CONF_HOST: DEFAULT_HOST,
            CONF_SSL: False,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if not user_input:
            user_input = {}

        data_schema = _user_schema_with_defaults(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {},
            description_placeholders=self.placeholders,
        )


    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form()

        host = user_input.get(CONF_HOST, self.placeholders[CONF_HOST])
        ssl = self.placeholders[CONF_SSL]
        password = user_input[CONF_PASSWORD]

        # Open connection and check authentication
        try:
            api = await self.hass.async_add_executor_job(
                get_api, password, host, ssl
            )
        except CannotLoginException:
            errors["base"] = "config"

        if errors:
            return await self._show_setup_form(user_input, errors)

        config_data = {
            CONF_PASSWORD: password,
            CONF_HOST: host,
            CONF_SSL: api.ssl,
        }

        # Check if already configured
        info = await self.hass.async_add_executor_job(api.get_device_info)
        await self.async_set_unique_id(info["SerialNumber"], raise_on_progress=False)
        self._abort_if_unique_id_configured(updates=config_data)

        name = info["ModelName"]

        return self.async_create_entry(
            title=name,
            data=config_data,
        )
