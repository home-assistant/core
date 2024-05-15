"""Config flow for Aurora ABB PowerOne integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aurorapy.client import AuroraError, AuroraSerialClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    DEFAULT_ADDRESS,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    MAX_ADDRESS,
    MIN_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_and_connect(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    comport = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Initialising com port=%s", comport)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.info("Returning device info=%s", ret)
    except AuroraError:
        _LOGGER.warning("Could not connect to device=%s", comport)
        raise
    finally:
        if client.serline.isOpen():
            client.close()

    # Return info we want to store in the config entry.
    return ret


def scan_comports() -> tuple[list[str] | None, str | None]:
    """Find and store available com ports for the GUI dropdown."""
    com_ports = serial.tools.list_ports.comports(include_links=True)
    com_ports_list = []
    for port in com_ports:
        com_ports_list.append(port.device)
        _LOGGER.debug("COM port option: %s", port.device)
    if len(com_ports_list) > 0:
        return com_ports_list, com_ports_list[0]
    _LOGGER.warning("No com ports found.  Need a valid RS485 device to communicate")
    return None, None


class AuroraABBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aurora ABB PowerOne."""

    VERSION = 1

    def __init__(self):
        """Initialise the config flow."""
        self.config = None
        self._com_ports_list = None
        self._default_com_port = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialised by the user."""

        errors = {}
        if self._com_ports_list is None:
            result = await self.hass.async_add_executor_job(scan_comports)
            self._com_ports_list, self._default_com_port = result
            if self._default_com_port is None:
                return self.async_abort(reason="no_serial_ports")

        # Handle the initial step.
        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect, self.hass, user_input
                )
            except OSError as error:
                if error.errno == 19:  # No such device.
                    errors["base"] = "invalid_serial_port"
            except AuroraError as error:
                if "could not open port" in str(error):
                    errors["base"] = "cannot_open_serial_port"
                elif "No response after" in str(error):
                    errors["base"] = "cannot_connect"  # could be dark
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_PORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
            else:
                info.update(user_input)
                # Bomb out early if someone has already set up this device.
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info)

        # If no user input, must be first pass through the config.  Show  initial form.
        config_options = {
            vol.Required(CONF_PORT, default=self._default_com_port): vol.In(
                self._com_ports_list
            ),
            vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
                range(MIN_ADDRESS, MAX_ADDRESS + 1)
            ),
        }
        schema = vol.Schema(config_options)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
