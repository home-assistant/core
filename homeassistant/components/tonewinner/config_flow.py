"""Config flow for the ToneWinner AT-500 integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import serial_asyncio_fast as serial_asyncio
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .const import CONF_BAUDRATE, DEFAULT_BAUDRATE, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): str,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): int,
    }
)


async def validate_serial_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the serial connection to the device.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    port = data[CONF_DEVICE]
    baudrate = data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)

    try:
        # Try to open serial connection
        reader, writer = await asyncio.wait_for(
            serial_asyncio.open_serial_connection(
                url=port, baudrate=baudrate, timeout=DEFAULT_TIMEOUT
            ),
            timeout=5.0,
        )
        writer.close()
        await writer.wait_closed()
    except (TimeoutError, OSError, serial_asyncio.SerialException) as err:
        _LOGGER.debug("Serial connection validation error: %s", err)
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {
        "title": f"AT-500 ({port})",
        CONF_DEVICE: port,
        CONF_BAUDRATE: baudrate,
    }


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ToneWinner AT-500."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_serial_connection(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{user_input[CONF_DEVICE]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
