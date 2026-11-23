"""Config flow for Antifurto365 iAlarm integration."""

import asyncio
import logging
from typing import Any, override

import probatio
from pyasyncialarm import IAlarm

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _get_device_mac(host: str, port: int) -> str:
    ialarm = IAlarm(host, port)
    try:
        async with asyncio.timeout(10):
            return await ialarm.get_mac()
    finally:
        await ialarm.shutdown()


class IAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Antifurto365 iAlarm."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        mac = None

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        try:
            # If we are able to get the MAC address, we are able to establish
            # a connection to the device.
            mac = await _get_device_mac(host, port)
        except TimeoutError, ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)
