"""Config flow for OpenHardwareMonitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession


from .const import *

_LOGGER = logging.getLogger(__name__)
DOMAIN = "openhardwaremonitor"


class OpenHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenHardwareMonitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        data_schema = vol.Schema(
            {vol.Required(CONNECTION_HOST): str, 
             vol.Required(CONNECTION_PORT): str,
             vol.Optional(GROUP_DEVICES_PER_DEPTH_LEVEL): int}
        )
        if user_input is None:
            return self.async_show_form(data_schema=data_schema)

        host = user_input[CONNECTION_HOST]
        port = user_input[CONNECTION_PORT]

        await self.async_set_unique_id(str(host) + str(port))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{host}:{port}",
            data=user_input,
        )
