"""Config flow for the London Air integration."""

from collections.abc import Mapping
from typing import Any, override

import aiohttp
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, REQUEST_TIMEOUT, URL


class LondonAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a London Air config flow."""

    VERSION = 1

    async def _test_connection(self) -> None:
        """Verify the API is reachable, raising on failure."""
        response = await async_get_clientsession(self.hass).get(
            URL, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

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
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                try:
                    await self._test_connection()
                except aiohttp.ClientError, TimeoutError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="London Air", data=user_input)

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
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        try:
            await self._test_connection()
        except aiohttp.ClientError, TimeoutError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title="London Air",
            data={CONF_LOCATIONS: list(import_config[CONF_LOCATIONS])},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_LOCATIONS]:
                errors[CONF_LOCATIONS] = "required"
            else:
                try:
                    await self._test_connection()
                except aiohttp.ClientError, TimeoutError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )

        default = (
            entry.data[CONF_LOCATIONS]
            if user_input is None
            else user_input[CONF_LOCATIONS]
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(default),
            errors=errors,
        )
