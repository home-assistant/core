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

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_connection(user_input: dict[str, Any]) -> str:
    """Ensure a connection can be established."""
    api = LibreHardwareMonitorClient(
        host=user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        username=user_input.get(CONF_USERNAME),
        password=user_input.get(CONF_PASSWORD),
    )

    return (await api.get_data()).computer_name


class LibreHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreHardwareMonitor."""

    VERSION = 2

    def __init__(self) -> None:
        """Init config flow."""

        self._host: str | None = None
        self._port: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            try:
                computer_name = await _validate_connection(user_input)
            except LibreHardwareMonitorConnectionError as exception:
                _LOGGER.error(exception)
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorUnauthorizedError:
                self._host = user_input[CONF_HOST]
                self._port = user_input[CONF_PORT]
                return await self.async_step_reauth_confirm()
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
        """Confirm (re)authentication dialog."""
        errors: dict[str, str] = {}

        # we use this step both for initial auth and for re-auth
        reauth_entry: ConfigEntry | None = None
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()

        if user_input:
            data = {
                CONF_HOST: reauth_entry.data[CONF_HOST] if reauth_entry else self._host,
                CONF_PORT: reauth_entry.data[CONF_PORT] if reauth_entry else self._port,
                **user_input,
            }
            try:
                computer_name = await _validate_connection(data)
            except LibreHardwareMonitorConnectionError as exception:
                _LOGGER.error(exception)
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorUnauthorizedError:
                errors["base"] = "invalid_auth"
            except LibreHardwareMonitorNoDevicesError:
                errors["base"] = "no_devices"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        entry=reauth_entry,  # type: ignore[arg-type]
                        data_updates=user_input,
                    )
                # the initial connection was unauthorized, now we can create the config entry
                return self.async_create_entry(
                    title=f"{computer_name} ({self._host}:{self._port})",
                    data=data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_USERNAME: user_input[CONF_USERNAME]
                    if user_input is not None
                    else reauth_entry.data.get(CONF_USERNAME)
                    if reauth_entry is not None
                    else None
                },
            ),
            errors=errors,
        )
