"""Config flow for Verizon FiOS Quantum Gateway integration."""

from collections.abc import Mapping
from typing import Any, override

from quantum_gateway import QuantumGatewayScanner
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_HOST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_SSL, default=True): cv.boolean,
        vol.Required(CONF_PASSWORD): str,
    }
)


def validate_connection_config(config: dict[str, Any]) -> None:
    """Validate that the provided configuration can connect to the Quantum Gateway."""
    scanner: QuantumGatewayScanner
    try:
        scanner = QuantumGatewayScanner(
            config[CONF_HOST], config[CONF_PASSWORD], config[CONF_SSL]
        )
    except RequestException as err:
        raise CannotConnect("Failed to connect to Quantum Gateway") from err

    if not scanner.success_init:
        raise CannotAuthenticate("Failed to authenticate to Quantum Gateway")


class QuantumGatewayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Quantum Gateway."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self.hass.async_add_executor_job(
                    validate_connection_config, user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )

                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user(self._get_reauth_entry().data.copy())

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle existing config import step."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self.hass.async_add_executor_job(
                validate_connection_config, import_data
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except CannotAuthenticate:
            return self.async_abort(reason="invalid_auth")

        return self.async_create_entry(
            title=f"{import_data[CONF_HOST]}", data=import_data
        )


class CannotConnect(Exception):
    """Custom exception for failing to connect to the Quantum Gateway."""


class CannotAuthenticate(Exception):
    """Custom exception for failing to authenticate to the Quantum Gateway."""
