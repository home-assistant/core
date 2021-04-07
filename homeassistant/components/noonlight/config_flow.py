"""Config flow for Noonlight integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PIN,
    CONF_MODE,
)

from .const import (
    CONF_ADDRESS_NAME,
    CONF_CITY,
    CONF_INSTRUCTIONS,
    CONF_PHONE,
    CONF_STATE,
    CONF_ZIPCODE,
    DOMAIN,
    CONF_SERVICES,
    CONF_SERVICES_LIST,
    CONF_MODE_LIST,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Noonlight."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the noonlight flow."""
        self._noonlight = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=DOMAIN,
                data={
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    CONF_NAME: user_input[CONF_ADDRESS_NAME],
                    CONF_ADDRESS: user_input[CONF_ADDRESS],
                    CONF_CITY: user_input[CONF_CITY],
                    CONF_STATE: user_input[CONF_STATE],
                    CONF_ZIPCODE: user_input[CONF_ZIPCODE],
                    CONF_SERVICES: user_input[CONF_SERVICES],
                    CONF_INSTRUCTIONS: user_input[CONF_INSTRUCTIONS],
                    CONF_PHONE: user_input[CONF_PHONE],
                    CONF_PIN: user_input[CONF_PIN],
                    CONF_MODE: user_input[CONF_MODE],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_TOKEN,
                    ): str,
                    vol.Required(
                        CONF_MODE,
                    ): vol.In(CONF_MODE_LIST),
                    vol.Required(
                        CONF_ADDRESS_NAME,
                    ): str,
                    vol.Required(
                        CONF_ADDRESS,
                    ): str,
                    vol.Required(
                        CONF_CITY,
                    ): str,
                    vol.Required(
                        CONF_STATE,
                    ): str,
                    vol.Required(
                        CONF_ZIPCODE,
                    ): str,
                    vol.Required(CONF_SERVICES): vol.In(CONF_SERVICES_LIST),
                    vol.Required(
                        CONF_INSTRUCTIONS,
                    ): str,
                    vol.Required(
                        CONF_PHONE,
                    ): str,
                    vol.Required(
                        CONF_PIN,
                    ): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
