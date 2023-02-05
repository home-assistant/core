"""Config flow for Sungrow Solar Energy integration."""
from __future__ import annotations

import logging
from typing import Any

from pysungrow import identify
from pysungrow.compat import AsyncModbusTcpClient
from pysungrow.identify import NotASungrowDeviceException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("port", default=502): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sungrow Solar Energy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                client = AsyncModbusTcpClient(user_input[CONF_HOST], port=502)
                serial_number, *_ = await identify(client, slave=1)
            except (NotASungrowDeviceException, ConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(updates=user_input)

                return self.async_create_entry(
                    title="Sungrow " + serial_number,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
