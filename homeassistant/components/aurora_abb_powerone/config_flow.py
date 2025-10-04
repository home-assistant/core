"""Config flow for Aurora ABB PowerOne integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, TypeVar

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant

from .aurora_client import AuroraClient, AuroraClientError
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

    _LOGGER.debug(
        "Trying to connect to inverter with address=%s via serial transport on comport='%s'",
        inverter_serial_address,
        serial_comport,
    )
    client = AuroraClient.from_serial(
        inverter_serial_address=inverter_serial_address, serial_comport=serial_comport
    )
    info = client.try_connect_and_fetch_identifier()

    # Return info we want to store in the config entry.
    return {
        "title": DEFAULT_INTEGRATION_TITLE,
        ATTR_SERIAL_NUMBER: info.serial_number,
        ATTR_MODEL: info.model,
        ATTR_FIRMWARE: info.firmware,
    }


def validate_and_connect_tcp(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect via tcp transport.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    tcp_host = data[CONF_TCP_HOST]
    tcp_port = data[CONF_TCP_PORT]
    inverter_serial_address = data[CONF_INVERTER_SERIAL_ADDRESS]

    _LOGGER.debug(
        "Trying to connect to inverter with address=%s via TCP transport on %s:%s",
        inverter_serial_address,
        tcp_host,
        tcp_port,
    )
    client = AuroraClient.from_tcp(
        inverter_serial_address=inverter_serial_address,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
    )
    info = client.try_connect_and_fetch_identifier()

    # Return info we want to store in the config entry.
    return {
        "title": DEFAULT_INTEGRATION_TITLE,
        ATTR_SERIAL_NUMBER: info.serial_number,
        ATTR_MODEL: info.model,
        ATTR_FIRMWARE: info.firmware,
    }


def scan_serial_comports() -> tuple[list[str] | None, str | None]:
    """Find and store available com ports for the GUI dropdown."""
    comports = serial.tools.list_ports.comports(include_links=True)
    comports_list = []
    for port in comports:
        comports_list.append(port.device)
        _LOGGER.debug("COM port option: %s", port.device)
    if len(comports_list) > 0:
        return comports_list, comports_list[0]
    _LOGGER.warning("No com ports found. Need a valid RS485 device to communicate")
    return None, None


class AuroraABBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aurora ABB PowerOne."""

    VERSION = 2

    _transport: str | None
    _serial_comport_list: list[str] | None
    _serial_comport_default: str | None

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._transport = None
        self._serial_comport_list = None
        self._serial_comport_default = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated step."""
        return await self.async_step_choose_transport(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration request from the user."""
        return await self.async_step_choose_transport(user_input)

    async def async_step_choose_transport(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose transport."""
        errors: dict[str, str] = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRANSPORT, default=self._get_default_transport()
                ): vol.In([TRANSPORT_SERIAL, TRANSPORT_TCP])
            }
        )

        if user_input is not None:
            self._transport = user_input[CONF_TRANSPORT]

            if self._transport == TRANSPORT_SERIAL:
                return await self.async_step_configure_serial()
            if self._transport == TRANSPORT_TCP:
                return await self.async_step_configure_tcp()

        return self.async_show_form(
            step_id="choose_transport", data_schema=schema, errors=errors
        )

    async def async_step_configure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Serial transport configuration step."""
        errors: dict[str, str] = {}

        if self._serial_comport_list is None:
            result = await self.hass.async_add_executor_job(scan_serial_comports)
            self._serial_comport_list, self._serial_comport_default = result
            if self._serial_comport_default is None:
                return self.async_abort(reason="no_serial_ports")
            if TYPE_CHECKING:
                assert isinstance(self._serial_comport_list, list)

        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect_serial, self.hass, user_input
                )
            except OSError as error:
                if error.errno == 19:  # No such device.
                    errors["base"] = "invalid_serial_port"
            except AuroraClientError as error:
                if "could not open port" in str(error):
                    errors["base"] = "cannot_open_serial_port"
                elif "No response after" in str(error):
                    errors["base"] = "cannot_connect"  # could be dark
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_SERIAL_COMPORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
            else:
                info.update(user_input)
                info[CONF_TRANSPORT] = TRANSPORT_SERIAL
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)

                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=info
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_COMPORT, default=self._get_default_serial_comport()
                ): vol.In(self._serial_comport_list),
                vol.Required(
                    CONF_INVERTER_SERIAL_ADDRESS,
                    default=self._get_default_inverter_serial_address(),
                ): vol.In(
                    range(INVERTER_SERIAL_ADDRESS_MIN, INVERTER_SERIAL_ADDRESS_MAX + 1)
                ),
            }
        )

        return self.async_show_form(
            step_id="configure_serial", data_schema=schema, errors=errors
        )

    async def async_step_configure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TCP transport configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect_tcp, self.hass, user_input
                )
            except AuroraClientError as error:
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

                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=info
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info)

        schema = vol.Schema(
            {
                vol.Required(CONF_TCP_HOST, default=self._get_default_tcp_host()): str,
                vol.Required(CONF_TCP_PORT, default=self._get_default_tcp_port()): int,
                vol.Required(
                    CONF_INVERTER_SERIAL_ADDRESS,
                    default=self._get_default_inverter_serial_address(),
                ): vol.In(
                    range(INVERTER_SERIAL_ADDRESS_MIN, INVERTER_SERIAL_ADDRESS_MAX + 1)
                ),
            }
        )

        return self.async_show_form(
            step_id="configure_tcp", data_schema=schema, errors=errors
        )

    def _get_default_transport(self) -> str:
        return self._get_or_default(CONF_TRANSPORT, TRANSPORT_SERIAL)

    def _get_default_inverter_serial_address(self) -> int:
        return self._get_or_default(
            CONF_INVERTER_SERIAL_ADDRESS, INVERTER_SERIAL_ADDRESS_DEFAULT
        )

    def _get_default_serial_comport(self) -> str | None:
        return self._get_or_default(CONF_SERIAL_COMPORT, self._serial_comport_default)

    def _get_default_tcp_host(self) -> str | None:
        return self._get_or_default(CONF_TCP_HOST, None)

    def _get_default_tcp_port(self) -> int:
        return self._get_or_default(CONF_TCP_PORT, TCP_PORT_DEFAULT)

    GetOrDefaultType = TypeVar("GetOrDefaultType")

    def _get_or_default(self, key: str, default: GetOrDefaultType) -> GetOrDefaultType:
        if self.source == SOURCE_RECONFIGURE:
            reconfigure_data = self._get_reconfigure_entry().data

            if key in reconfigure_data:
                return reconfigure_data[key]

        return default
