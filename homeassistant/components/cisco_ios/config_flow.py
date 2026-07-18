"""Config flow for the Cisco IOS integration."""

from typing import Any, override

from pexpect import pxssh
import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import CiscoIOSArpScanner

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_PORT): cv.port,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME.total_seconds()
        ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=900)),
    }
)


def validate_connection_data(data: dict[str, Any]) -> None:
    """Validate that we can connect to the router with the provided configuration."""
    scanner = CiscoIOSArpScanner(
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        port=data.get(CONF_PORT),
    )
    try:
        scanner.get_devices()
    except pxssh.ExceptionPxssh as err:
        raise CannotConnect("Failed to connect to Cisco IOS router") from err


class CiscoIOSOptionsFlow(OptionsFlowWithReload):
    """Handle an options flow for Cisco IOS."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class CiscoIOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cisco IOS."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CiscoIOSOptionsFlow:
        """Get the options flow for this handler."""
        return CiscoIOSOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self.hass.async_add_executor_job(
                    validate_connection_data, user_input
                )
            except CannotConnect:
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
        """Import existing config from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        # Clamp to the range the options flow enforces
        consider_home: int = min(import_data.pop(CONF_CONSIDER_HOME), 900)

        try:
            await self.hass.async_add_executor_job(
                validate_connection_data, import_data
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({import_data[CONF_HOST]})",
            data=import_data,
            options={CONF_CONSIDER_HOME: consider_home},
        )


class CannotConnect(Exception):
    """Custom exception for failing to connect to the Cisco IOS router."""
