"""Config flow for UniFi AP Direct integration."""

from typing import Any, override

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_NAME, DEFAULT_SSH_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
    }
)


def validate_connection_data(data: dict[str, Any]) -> None:
    """Validate that we can connect to the UniFi AP with the provided configuration."""
    try:
        ap = UniFiAP(
            target=data[CONF_HOST],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            port=data[CONF_PORT],
        )
        ap.get_clients()
    except (UniFiAPConnectionException, UniFiAPDataException) as err:
        raise CannotConnect("Failed to connect to UniFi AP") from err


class UniFiDirectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Direct."""

    VERSION = 1

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

        try:
            await self.hass.async_add_executor_job(
                validate_connection_data, import_data
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({import_data[CONF_HOST]})",
            data=import_data,
        )


class CannotConnect(Exception):
    """Custom exception for failing to connect to the UniFiAP."""
