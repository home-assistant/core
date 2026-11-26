"""Config flow for the Sony TV RS-232 integration."""

import asyncio
from typing import Any, override

import probatio
from sony_tv_rs232 import SerialKitError, SonyTV

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.helpers.selector import SerialPortSelector

from .const import DOMAIN, LOGGER

# Bound the port open so an unreachable socket:// or esphome:// URL surfaces as
# cannot_connect instead of hanging the flow. With refresh_on_connect=False the
# handshake is the power probe and the standby-listen arm: at most a few paced
# 2 s timeouts, well inside this budget.
_CONNECT_TIMEOUT = 15.0

# SerialPortSelector lists the host's serial ports plus remote ports from
# ESPHome serial proxies; requires "usb" in the manifest dependencies.
STEP_USER_SCHEMA = probatio.Schema({probatio.Required(CONF_PORT): SerialPortSelector()})


def _loggable_port(port: str) -> str:
    """Strip the query from a port URL: an esphome:// URL can carry its API key."""
    return port.split("?", 1)[0]


async def _async_attempt_connect(port: str) -> str | None:
    """Try to open the port and run the handshake.

    Returns None on success, otherwise the error key for the form. Sony's
    protocol has no ping and consumer Bravia TVs ignore query packets, so this
    can only prove the port opens; a wiring problem surfaces later as commands
    that are never acknowledged.
    """
    tv = SonyTV(port, refresh_on_connect=False)
    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT):
            await tv.connect()
    except SerialKitError, OSError, ValueError, TimeoutError:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception opening %s", _loggable_port(port))
        return "unknown"
    else:
        await tv.disconnect()
        return None


class SonyTVRS232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the serial port the TV is wired to."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT]
            self._async_abort_entries_match({CONF_PORT: port})
            error = await _async_attempt_connect(port)
            if error is None:
                # A second flow for the same port may have finished while
                # this one was connecting.
                self._async_abort_entries_match({CONF_PORT: port})
                return self.async_create_entry(
                    title="Sony TV",
                    data={CONF_PORT: port},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )
