"""Config flow for Aurora ABB PowerOne integration."""

from __future__ import annotations

import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .aurora_client import AuroraClient, AuroraClientError, AuroraInverterIdentifier
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


def validate_and_connect_serial(data: dict[str, Any]) -> AuroraInverterIdentifier:
    """Validate serial connection and fetch inverter identifier."""
    _LOGGER.debug(
        "Initialising serial connection on port=%s", data[CONF_SERIAL_COMPORT]
    )
    client = AuroraClient.from_serial(
        inverter_serial_address=data[CONF_INVERTER_SERIAL_ADDRESS],
        serial_comport=data[CONF_SERIAL_COMPORT],
    )
    return client.try_connect_and_fetch_identifier()


def validate_and_connect_tcp(data: dict[str, Any]) -> AuroraInverterIdentifier:
    """Validate TCP connection and fetch inverter identifier."""
    _LOGGER.debug(
        "Initialising TCP connection to %s:%s", data[CONF_TCP_HOST], data[CONF_TCP_PORT]
    )
    client = AuroraClient.from_tcp(
        inverter_serial_address=data[CONF_INVERTER_SERIAL_ADDRESS],
        tcp_host=data[CONF_TCP_HOST],
        tcp_port=data[CONF_TCP_PORT],
    )
    return client.try_connect_and_fetch_identifier()


def scan_serial_comports() -> tuple[list[str] | None, str | None]:
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
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._transport: str | None = None
        self._com_ports_list: list[str] | None = None
        self._default_com_port: str | None = None

    def _get_or_default(self, key: str, default: Any = None) -> Any:
        """Return existing config entry value for reconfigure, or default."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry().data.get(key, default)
        return default

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialised by the user."""
        return await self.async_step_choose_transport(user_input)

    async def async_step_choose_transport(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle transport selection step."""
        if user_input is not None:
            self._transport = user_input[CONF_TRANSPORT]
            if self._transport == TRANSPORT_SERIAL:
                return await self.async_step_configure_serial()
            return await self.async_step_configure_tcp()

        return self.async_show_form(
            step_id="choose_transport",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TRANSPORT,
                        default=self._get_or_default(CONF_TRANSPORT, TRANSPORT_SERIAL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[TRANSPORT_SERIAL, TRANSPORT_TCP],
                            mode=SelectSelectorMode.LIST,
                            translation_key=CONF_TRANSPORT,
                        )
                    ),
                }
            ),
        )

    async def async_step_configure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle serial transport configuration step."""
        errors: dict[str, str] = {}

        if self._com_ports_list is None:
            result = await self.hass.async_add_executor_job(scan_serial_comports)
            self._com_ports_list, self._default_com_port = result
            if self._default_com_port is None:
                return self.async_abort(reason="no_serial_ports")

        if user_input is not None:
            try:
                identifier = await self.hass.async_add_executor_job(
                    validate_and_connect_serial, user_input
                )
            except OSError as error:
                if error.errno == 19:  # No such device
                    errors["base"] = "invalid_serial_port"
                else:
                    errors["base"] = "cannot_connect"
            except AuroraClientError as error:
                if "could not open port" in str(error):
                    errors["base"] = "cannot_open_serial_port"
                else:
                    errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_TRANSPORT: TRANSPORT_SERIAL,
                    CONF_INVERTER_SERIAL_ADDRESS: user_input[
                        CONF_INVERTER_SERIAL_ADDRESS
                    ],
                    CONF_SERIAL_COMPORT: user_input[CONF_SERIAL_COMPORT],
                    ATTR_SERIAL_NUMBER: identifier.serial_number,
                    ATTR_MODEL: identifier.model,
                    ATTR_FIRMWARE: identifier.firmware,
                }
                return await self._async_finish_flow(identifier.serial_number, data)

        default_comport = self._get_or_default(
            CONF_SERIAL_COMPORT, self._default_com_port
        )
        default_address = self._get_or_default(
            CONF_INVERTER_SERIAL_ADDRESS, INVERTER_SERIAL_ADDRESS_DEFAULT
        )

        assert self._com_ports_list is not None
        return self.async_show_form(
            step_id="configure_serial",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERIAL_COMPORT, default=default_comport
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=self._com_ports_list,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(
                        CONF_INVERTER_SERIAL_ADDRESS, default=default_address
                    ): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=INVERTER_SERIAL_ADDRESS_MIN,
                                max=INVERTER_SERIAL_ADDRESS_MAX,
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_configure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle TCP transport configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                identifier = await self.hass.async_add_executor_job(
                    validate_and_connect_tcp, user_input
                )
            except AuroraClientError:
                errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_TRANSPORT: TRANSPORT_TCP,
                    CONF_INVERTER_SERIAL_ADDRESS: user_input[
                        CONF_INVERTER_SERIAL_ADDRESS
                    ],
                    CONF_TCP_HOST: user_input[CONF_TCP_HOST],
                    CONF_TCP_PORT: user_input[CONF_TCP_PORT],
                    ATTR_SERIAL_NUMBER: identifier.serial_number,
                    ATTR_MODEL: identifier.model,
                    ATTR_FIRMWARE: identifier.firmware,
                }
                return await self._async_finish_flow(identifier.serial_number, data)

        default_address = self._get_or_default(
            CONF_INVERTER_SERIAL_ADDRESS, INVERTER_SERIAL_ADDRESS_DEFAULT
        )
        default_host = self._get_or_default(CONF_TCP_HOST, "")
        default_port = self._get_or_default(CONF_TCP_PORT, TCP_PORT_DEFAULT)

        return self.async_show_form(
            step_id="configure_tcp",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TCP_HOST, default=default_host): str,
                    vol.Required(CONF_TCP_PORT, default=default_port): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=1,
                                max=65535,
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                    vol.Required(
                        CONF_INVERTER_SERIAL_ADDRESS, default=default_address
                    ): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=INVERTER_SERIAL_ADDRESS_MIN,
                                max=INVERTER_SERIAL_ADDRESS_MAX,
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_finish_flow(
        self, serial_number: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Finish the flow by creating or updating the config entry."""
        await self.async_set_unique_id(serial_number)

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=data,
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=DEFAULT_INTEGRATION_TITLE, data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        return await self.async_step_choose_transport(user_input)
