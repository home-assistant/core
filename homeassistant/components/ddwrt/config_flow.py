"""Config flow for the DD-WRT integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_WIRELESS_ONLY,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WIRELESS_ONLY,
    DOMAIN,
)
from .router import DdWrtConnectionError, DdWrtRouter

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_WIRELESS_ONLY, default=DEFAULT_WIRELESS_ONLY): cv.boolean,
    }
)


def _validate_connection(data: dict[str, Any]) -> None:
    """Validate that we can connect to the DD-WRT router."""
    router = DdWrtRouter(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        use_ssl=data[CONF_SSL],
        verify_ssl=data[CONF_VERIFY_SSL],
        wireless_only=data[CONF_WIRELESS_ONLY],
    )
    router.get_clients()


class DdWrtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DD-WRT."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self.hass.async_add_executor_job(_validate_connection, user_input)
            except DdWrtConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import existing configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        try:
            await self.hass.async_add_executor_job(_validate_connection, import_data)
        except DdWrtConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({import_data[CONF_HOST]})",
            data=import_data,
        )
