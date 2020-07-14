"""Config flow for DSMR integration."""
import asyncio
from functools import partial
import logging

from dsmr_parser import obis_references as obis_ref
from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
import serial
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_FORCE_UPDATE, CONF_HOST, CONF_PORT, CONF_TYPE

# pylint: disable=unused-import
from .const import (
    CONF_DSMR_VERSION,
    CONF_POWER_WATT,
    CONF_PRECISION,
    CONF_RECONNECT_INTERVAL,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_POWER_WATT,
    DEFAULT_PRECISION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DSMRConnection:
    """Test the connection to DSMR and receive telegram to read serial ids."""

    def __init__(self, host, port, dsmr_version):
        """Initialize."""
        self._host = host
        self._port = port
        self._dsmr_version = dsmr_version
        self._telegram = {}

    def equipment_identifier(self):
        """Equipment identifier."""
        if obis_ref.EQUIPMENT_IDENTIFIER in self._telegram:
            dsmr_object = self._telegram[obis_ref.EQUIPMENT_IDENTIFIER]
            return getattr(dsmr_object, "value", None)

    def equipment_identifier_gas(self):
        """Equipment identifier gas."""
        if obis_ref.EQUIPMENT_IDENTIFIER_GAS in self._telegram:
            dsmr_object = self._telegram[obis_ref.EQUIPMENT_IDENTIFIER_GAS]
            return getattr(dsmr_object, "value", None)

    async def validate_connect(self, hass: core.HomeAssistant) -> bool:
        """Test if we can validate connection with the device."""

        def update_telegram(telegram):
            self._telegram = telegram

            transport.close()

        if self._host is None:
            reader_factory = partial(
                create_dsmr_reader,
                self._port,
                self._dsmr_version,
                update_telegram,
                loop=hass.loop,
            )
        else:
            reader_factory = partial(
                create_tcp_dsmr_reader,
                self._host,
                self._port,
                self._dsmr_version,
                update_telegram,
                loop=hass.loop,
            )

        try:
            transport, protocol = await hass.loop.create_task(reader_factory())
        except (
            serial.serialutil.SerialException,
            ConnectionRefusedError,
            TimeoutError,
            asyncio.TimeoutError,
        ):
            _LOGGER.exception("Error connecting to DSMR")
            return False

        if transport:
            await protocol.wait_closed()

        return True


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    conn = DSMRConnection(data[CONF_HOST], data[CONF_PORT], data[CONF_DSMR_VERSION])

    if not await conn.validate_connect(hass):
        raise CannotConnect

    equipment_identifier = conn.equipment_identifier()
    equipment_identifier_gas = conn.equipment_identifier_gas()

    if equipment_identifier is None:
        raise CannotCommunicate

    info = {
        CONF_SERIAL_ID: equipment_identifier,
        CONF_SERIAL_ID_GAS: equipment_identifier_gas,
    }

    return info


class DSMRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSMR."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow instance."""
        self._host = None
        self._port = None
        self._dsmr_version = None
        self._serial_id = None
        self._serial_id_gas = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            user_selection = user_input[CONF_TYPE]
            self._dsmr_version = user_input[CONF_DSMR_VERSION]
            if user_selection == "Serial":
                return await self.async_step_setup_serial()

            return await self.async_step_setup_host()

        list_of_types = ["Serial", "Host"]

        schema = vol.Schema(
            {
                vol.Required(CONF_TYPE): vol.In(list_of_types),
                vol.Required(CONF_DSMR_VERSION): vol.In(["5B", "5", "4", "2.2"]),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_setup_serial(self, user_input=None):
        """Select options for serial connection."""
        errors = {}
        if user_input is not None:
            self._port = user_input[CONF_PORT]

            try:
                data = {
                    CONF_PORT: self._port,
                    CONF_HOST: self._host,
                    CONF_DSMR_VERSION: self._dsmr_version,
                }

                info = await validate_input(self.hass, data)

                self._serial_id = info[CONF_SERIAL_ID]
                self._serial_id_gas = info[CONF_SERIAL_ID_GAS]

                return await self.async_step_setup_options()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotCommunicate:
                errors["base"] = "cannot_communicate"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        schema = vol.Schema({vol.Required(CONF_PORT): str})
        return self.async_show_form(
            step_id="setup_serial", data_schema=schema, errors=errors
        )

    async def async_step_setup_host(self, user_input=None):
        """Select options for host connection."""
        errors = {}
        if user_input is not None:
            self._port = user_input[CONF_PORT]
            self._host = user_input[CONF_HOST]

            try:
                data = {
                    CONF_PORT: self._port,
                    CONF_HOST: self._host,
                    CONF_DSMR_VERSION: self._dsmr_version,
                }

                info = await validate_input(self.hass, data)

                self._serial_id = info[CONF_SERIAL_ID]
                self._serial_id_gas = info[CONF_SERIAL_ID_GAS]

                return await self.async_step_setup_options()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotCommunicate:
                errors["base"] = "cannot_communicate"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        schema = vol.Schema(
            {vol.Required(CONF_HOST): str, vol.Required(CONF_PORT): int}
        )
        return self.async_show_form(
            step_id="setup_host", data_schema=schema, errors=errors
        )

    async def async_step_setup_options(self, user_input=None):
        """Select optional options."""
        errors = {}
        if user_input is not None:
            if self._host is None:
                name = self._port
            else:
                name = f"{self._host}:{self._port}"

            return self.async_create_entry(
                title=name,
                data={
                    CONF_DSMR_VERSION: self._dsmr_version,
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_RECONNECT_INTERVAL: user_input.get(CONF_RECONNECT_INTERVAL),
                    CONF_PRECISION: user_input.get(CONF_PRECISION),
                    CONF_FORCE_UPDATE: user_input.get(CONF_FORCE_UPDATE),
                    CONF_POWER_WATT: user_input.get(CONF_POWER_WATT),
                    CONF_SERIAL_ID: self._serial_id,
                    CONF_SERIAL_ID_GAS: self._serial_id_gas,
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_RECONNECT_INTERVAL, default=30): int,
                vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): int,
                vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): bool,
                vol.Optional(CONF_POWER_WATT, default=DEFAULT_POWER_WATT): bool,
            }
        )

        return self.async_show_form(
            step_id="setup_options", data_schema=schema, errors=errors
        )

    def usb_already_configured(self, port):
        """See if we already have a DSMR USB entry matching user input configured."""
        existing_usb = {
            entry.data[CONF_PORT] for entry in self._async_current_entries()
        }
        return port in existing_usb

    def host_already_configured(self, host, port):
        """See if we already have a DSMR Host entry matching user input configured."""
        for entry in self._async_current_entries():
            if (
                entry.data[CONF_HOST] == self._host
                and entry.data[CONF_PORT] == self._port
            ):
                return True

        return False


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class CannotCommunicate(exceptions.HomeAssistantError):
    """Error to indicate we cannot communicate with device."""
