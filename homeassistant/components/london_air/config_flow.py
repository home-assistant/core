"""Config flow for the London Air integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pylondonair import LondonAirClient, LondonAirConnectionError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, INTEGRATION_TITLE


class LondonAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a London Air config flow."""

    VERSION = 1

    async def _async_test_connection(self) -> None:
        """Verify the API is reachable, raising on failure."""
        client = LondonAirClient(session=async_get_clientsession(self.hass))
        await client.async_test_connection()

    def _schema(self, default: list[str]) -> probatio.Schema:
        """Build the locations selection schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_LOCATIONS, default=default): cv.multi_select(
                    AUTHORITIES
                )
            }
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_LOCATIONS]:
                errors[CONF_LOCATIONS] = "required"
            else:
                try:
                    await self._async_test_connection()
                except LondonAirConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=INTEGRATION_TITLE, data=user_input
                    )

        default = AUTHORITIES if user_input is None else user_input[CONF_LOCATIONS]
        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(default),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        try:
            await self._async_test_connection()
        except LondonAirConnectionError:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(
            title=INTEGRATION_TITLE,
            data={CONF_LOCATIONS: list(import_config[CONF_LOCATIONS])},
        )
