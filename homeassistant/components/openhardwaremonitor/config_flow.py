"""Config flow for OpenHardwareMonitor integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, GROUP_DEVICES_PER_DEPTH_LEVEL


class OpenHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenHardwareMonitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle default config flow."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=8085): cv.port,
                vol.Optional(GROUP_DEVICES_PER_DEPTH_LEVEL, default=2): int,
            }
        )
        if user_input is None:
            return self.async_show_form(data_schema=data_schema)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{host}:{port}",
            data=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        config_entry = self._get_reconfigure_entry()
        data = dict(config_entry.data)
        current_device_grouping = data.get(GROUP_DEVICES_PER_DEPTH_LEVEL, 0)
        data_schema = vol.Schema(
            {
                vol.Optional(
                    GROUP_DEVICES_PER_DEPTH_LEVEL, default=current_device_grouping
                ): int,
            }
        )
        if user_input is None:
            return self.async_show_form(data_schema=data_schema)

        return self.async_update_reload_and_abort(
            config_entry,
            data_updates={
                GROUP_DEVICES_PER_DEPTH_LEVEL: user_input.get(
                    GROUP_DEVICES_PER_DEPTH_LEVEL, current_device_grouping
                )
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import config from configuration.yaml."""
        host = import_data[CONF_HOST]
        port = import_data[CONF_PORT]
        if import_data.get(GROUP_DEVICES_PER_DEPTH_LEVEL) is None:
            import_data[GROUP_DEVICES_PER_DEPTH_LEVEL] = 0

        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        title = f"{host}:{port}"
        return self.async_create_entry(
            title=title,
            data=import_data,
        )
