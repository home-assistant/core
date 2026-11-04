"""Config flow for the London Air integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pylondonair import LondonAirClient, LondonAirConnectionError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, INTEGRATION_TITLE

SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_LOCATIONS): SelectSelector(
            SelectSelectorConfig(
                options=AUTHORITIES,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                sort=True,
            )
        )
    }
)


class LondonAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a London Air config flow."""

    VERSION = 1

    async def _async_test_connection(self) -> None:
        """Verify the API is reachable, raising on failure."""
        client = LondonAirClient(session=async_get_clientsession(self.hass))
        await client.async_test_connection()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        if user_input is None:
            try:
                await self._async_test_connection()
            except LondonAirConnectionError:
                return self.async_abort(reason="cannot_connect")
        elif not user_input[CONF_LOCATIONS]:
            errors[CONF_LOCATIONS] = "required"
        else:
            return self.async_create_entry(title=INTEGRATION_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                SCHEMA,
                {
                    CONF_LOCATIONS: (
                        user_input[CONF_LOCATIONS]
                        if user_input is not None
                        else AUTHORITIES
                    )
                },
            ),
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
