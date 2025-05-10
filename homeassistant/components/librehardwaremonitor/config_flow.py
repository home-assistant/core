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


class LibreHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreHardwareMonitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        config_data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            api = LibreHardwareMonitorClient(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )

            try:
                _ = (await api.get_data()).main_device_names
            except LibreHardwareMonitorConnectionError:
                errors["base"] = "cannot_connect"
            except LibreHardwareMonitorNoDevicesError:
                errors["base"] = "no_devices"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=config_data_schema, errors=errors
        )
