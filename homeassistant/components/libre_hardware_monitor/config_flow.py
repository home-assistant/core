"""Config flow for LibreHardwareMonitor."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
    LibreHardwareMonitorUnauthorizedError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _validate_credentials(user_input: dict[str, Any], errors: dict[str, str]) -> bool:
    """Ensure both username and password are provided, populate errors if needed."""
    authentication = CONF_USERNAME in user_input or CONF_PASSWORD in user_input
    if authentication and CONF_USERNAME not in user_input:
        errors["base"] = "username_missing"
        return False
    if authentication and CONF_PASSWORD not in user_input:
        errors["base"] = "password_missing"
        return False
    return True


class LibreHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreHardwareMonitor."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if _validate_credentials(user_input, errors):
                self._async_abort_entries_match(user_input)

                api = LibreHardwareMonitorClient(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    username=user_input.get(CONF_USERNAME),
                    password=user_input.get(CONF_PASSWORD),
                )

                try:
                    computer_name = (await api.get_data()).computer_name
                except LibreHardwareMonitorConnectionError as exception:
                    _LOGGER.error(exception)
                    errors["base"] = "cannot_connect"
                except LibreHardwareMonitorUnauthorizedError:
                    errors["base"] = "invalid_auth"
                except LibreHardwareMonitorNoDevicesError:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"{computer_name} ({user_input[CONF_HOST]}:{user_input[CONF_PORT]})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input:
            api = LibreHardwareMonitorClient(
                host=reauth_entry.data[CONF_HOST],
                port=reauth_entry.data[CONF_PORT],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )

            try:
                _ = await api.get_data()
            except LibreHardwareMonitorConnectionError as exception:
                _LOGGER.error(exception)
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorUnauthorizedError:
                errors["base"] = "invalid_auth"
            except LibreHardwareMonitorNoDevicesError:
                errors["base"] = "no_devices"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_USERNAME: user_input[CONF_USERNAME]
                    if user_input is not None
                    else reauth_entry.data.get(CONF_USERNAME)
                },
            ),
            errors=errors,
        )
