"""Config flow for Aurora ABB PowerOne integration."""

from __future__ import annotations

from collections.abc import Mapping
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from aurorapy.client import AuroraError, AuroraSerialClient, AuroraTCPClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    INVERTER_SERIAL_ADDRESS_DEFAULT,
    INVERTER_SERIAL_ADDRESS_MAX,
    INVERTER_SERIAL_ADDRESS_MIN,
    TCP_PORT_DEFAULT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)

_LOGGER = logging.getLogger(__name__)


def validate_and_connect_serial(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect via serial transport.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    serial_comport = data[CONF_SERIAL_COMPORT]
    inverter_serial_address = data[CONF_INVERTER_SERIAL_ADDRESS]
    _LOGGER.debug("Initialising serial com port=%s", serial_comport)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraSerialClient(
            inverter_serial_address, serial_comport, parity="N", timeout=1
        )
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.debug("Returning device info=%s", ret)
    except AuroraError:
        _LOGGER.warning("Could not connect to device=%s", serial_comport)
        raise
    finally:
        with contextlib.suppress(Exception):
            client.close()

    # Return info we want to store in the config entry.
    return ret


def validate_and_connect_tcp(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect via tcp transport.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    tcp_host = data[CONF_TCP_HOST]
    tcp_port = data[CONF_TCP_PORT]
    inverter_serial_address = data[CONF_INVERTER_SERIAL_ADDRESS]
    _LOGGER.debug("Initialising TCP host=%s port=%s", tcp_host, tcp_port)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraTCPClient(tcp_host, tcp_port, inverter_serial_address, timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.debug("Returning device info (TCP)=%s", ret)
    except AuroraError:
        _LOGGER.warning(
            "Could not connect to device over TCP at %s:%s", tcp_host, tcp_port
        )
        raise
    finally:
        with contextlib.suppress(Exception):
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
    _LOGGER.warning("No com ports found. Need a valid RS485 device to communicate")
    return None, None


class AuroraABBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aurora ABB PowerOne."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._com_ports_list: list[str] | None = None
        self._default_com_port: str | None = None
        self._transport: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: choose transport."""
        errors: dict[str, str] = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_TRANSPORT, default=TRANSPORT_SERIAL): vol.In(
                    [TRANSPORT_SERIAL, TRANSPORT_TCP]
                )
            }
        )

        if user_input is not None:
            self._transport = user_input[CONF_TRANSPORT]
            if self._transport == TRANSPORT_TCP:
                return await self.async_step_tcp()
            return await self.async_step_serial()

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Serial configuration step."""
        errors: dict[str, str] = {}

        if self._com_ports_list is None:
            result = await self.hass.async_add_executor_job(scan_comports)
            self._com_ports_list, self._default_com_port = result
            if self._default_com_port is None:
                return self.async_abort(reason="no_serial_ports")
            if TYPE_CHECKING:
                assert isinstance(self._com_ports_list, list)

        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect_serial, self.hass, user_input
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
                        user_input.get(CONF_SERIAL_COMPORT),
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
            else:
                info.update(user_input)
                info[CONF_TRANSPORT] = TRANSPORT_SERIAL
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info)

        # initial / retry form
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_COMPORT, default=self._default_com_port
                ): vol.In(self._com_ports_list),
                vol.Required(
                    CONF_INVERTER_SERIAL_ADDRESS,
                    default=INVERTER_SERIAL_ADDRESS_DEFAULT,
                ): vol.In(
                    range(INVERTER_SERIAL_ADDRESS_MIN, INVERTER_SERIAL_ADDRESS_MAX + 1)
                ),
            }
        )
        return self.async_show_form(step_id="serial", data_schema=schema, errors=errors)

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TCP configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect_tcp, self.hass, user_input
                )
            except AuroraError as error:
                _LOGGER.error(
                    "Unable to communicate with Aurora ABB Inverter over TCP at %s:%s: %s %s",
                    user_input.get(CONF_TCP_HOST),
                    user_input.get(CONF_TCP_PORT),
                    type(error),
                    error,
                )
                errors["base"] = "cannot_connect"
            else:
                info.update(user_input)
                info[CONF_TRANSPORT] = TRANSPORT_TCP
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info)

        schema = vol.Schema(
            {
                vol.Required(CONF_TCP_HOST): str,
                vol.Required(CONF_TCP_PORT, default=TCP_PORT_DEFAULT): int,
                vol.Required(
                    CONF_INVERTER_SERIAL_ADDRESS,
                    default=INVERTER_SERIAL_ADDRESS_DEFAULT,
                ): vol.In(
                    range(INVERTER_SERIAL_ADDRESS_MIN, INVERTER_SERIAL_ADDRESS_MAX + 1)
                ),
            }
        )
        return self.async_show_form(step_id="tcp", data_schema=schema, errors=errors)
