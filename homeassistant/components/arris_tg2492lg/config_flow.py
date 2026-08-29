"""Config flow for the Arris TG2492LG integration."""

from typing import Any, override

from aiohttp.client_exceptions import ClientError
from arris_tg2492lg import ConnectBox
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class ArrisTG2492LGConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arris TG2492LG."""

    VERSION = 1

    async def _async_validate_input(self, data: dict[str, Any]) -> None:
        """Validate that we can connect to the router with the provided configuration."""
        connect_box = ConnectBox(
            async_get_clientsession(self.hass),
            f"http://{data[CONF_HOST]}",
            data[CONF_PASSWORD],
        )
        await connect_box.async_login()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self._async_validate_input(user_input)
            except ClientError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Arris TG2492LG ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import existing config from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self._async_validate_input(import_data)
        except ClientError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"Arris TG2492LG ({import_data[CONF_HOST]})",
            data=import_data,
        )
