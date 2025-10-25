"""Config flow for LibreHardwareMonitor."""

from __future__ import annotations

import logging
from typing import Any

from librehardwaremonitor_api import (
    LibreHardwareMonitorClient,
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class LibreHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreHardwareMonitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            api = LibreHardwareMonitorClient(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )

            try:
                _ = (await api.get_data()).main_device_ids_and_names.values()
            except LibreHardwareMonitorConnectionError as exception:
                _LOGGER.error(exception)
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorNoDevicesError:
                errors["base"] = "no_devices"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
