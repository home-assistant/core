"""
Support for Modbus.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/modbus/
"""
import logging
import threading
from typing import TYPE_CHECKING, Any, List

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_STATE, CONF_HOST, CONF_METHOD, CONF_PORT, CONF_TIMEOUT, CONF_TYPE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from pymodbus.client.sync import BaseModbusClient

DOMAIN = "modbus"

REQUIREMENTS = ["pymodbus==1.3.1"]

# Type of network
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_STOPBITS = "stopbits"
CONF_PARITY = "parity"
CONF_HUB_NAME = "hub_name"

BASE_SCHEMA = vol.Schema({
    vol.Optional(CONF_HUB_NAME, default="default"): cv.string
})

SERIAL_SCHEMA = BASE_SCHEMA.extend({
    vol.Required(CONF_BAUDRATE): cv.positive_int,
    vol.Required(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
    vol.Required(CONF_METHOD): vol.Any("rtu", "ascii"),
    vol.Required(CONF_PORT): cv.string,
    vol.Required(CONF_PARITY): vol.Any("E", "O", "N"),
    vol.Required(CONF_STOPBITS): vol.Any(1, 2),
    vol.Required(CONF_TYPE): "serial",
    vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
})

ETHERNET_SCHEMA = BASE_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_TYPE): vol.Any("tcp", "udp", "rtuovertcp"),
    vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
})


def check_base_on_type(value: Any) -> Any:
    """Check modbus component schema base on "type"."""
    if value[CONF_TYPE] == "serial":
        return SERIAL_SCHEMA(value)
    if value[CONF_TYPE] in ("tcp", "udp", "rtuovertcp"):
        return ETHERNET_SCHEMA(value)

    raise vol.Invalid("%s %s is not supported" % (CONF_TYPE, value[CONF_TYPE]))


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
            vol.All(cv.ensure_list,
                    vol.Schema([vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA)]))
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_REGISTER = "write_register"
SERVICE_WRITE_COIL = "write_coil"

ATTR_ADDRESS = "address"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema({
    vol.Optional(CONF_HUB_NAME, default="default"): cv.string,
    vol.Required(ATTR_UNIT): cv.positive_int,
    vol.Required(ATTR_ADDRESS): cv.positive_int,
    vol.Required(ATTR_VALUE): vol.All(cv.ensure_list, [cv.positive_int]),
})

SERVICE_WRITE_COIL_SCHEMA = vol.Schema({
    vol.Optional(CONF_HUB_NAME, default="default"): cv.string,
    vol.Required(ATTR_UNIT): cv.positive_int,
    vol.Required(ATTR_ADDRESS): cv.positive_int,
    vol.Required(ATTR_STATE): cv.boolean,
})


def setup_client(client_config: dict) -> "BaseModbusClient":
    """Setup pymodbus client."""
    from pymodbus.client.sync import (
        ModbusTcpClient,
        ModbusUdpClient,
        ModbusSerialClient,
    )
    from pymodbus.transaction import ModbusRtuFramer

    client_type = client_config[CONF_TYPE]

    # Connect to Modbus network
    # pylint: disable=import-error

    if client_type == "serial":

        return ModbusSerialClient(
            method=client_config[CONF_METHOD],
            port=client_config[CONF_PORT],
            baudrate=client_config[CONF_BAUDRATE],
            stopbits=client_config[CONF_STOPBITS],
            bytesize=client_config[CONF_BYTESIZE],
            parity=client_config[CONF_PARITY],
            timeout=client_config[CONF_TIMEOUT],
        )
    if client_type == "rtuovertcp":

        return ModbusTcpClient(
            host=client_config[CONF_HOST],
            port=client_config[CONF_PORT],
            framer=ModbusRtuFramer,
            timeout=client_config[CONF_TIMEOUT],
        )
    if client_type == "tcp":
        return ModbusTcpClient(
            host=client_config[CONF_HOST],
            port=client_config[CONF_PORT],
            timeout=client_config[CONF_TIMEOUT],
        )
    if client_type == "udp":
        return ModbusUdpClient(
            host=client_config[CONF_HOST],
            port=client_config[CONF_PORT],
            timeout=client_config[CONF_TIMEOUT],
        )

    assert False


def setup(hass: Any, config: dict) -> bool:
    """Set up Modbus component."""
    # Modbus connection type
    hass.data[DOMAIN] = hub_collect = {}

    for client_config in config[DOMAIN]:
        client = setup_client(client_config)
        client_name = client_config[CONF_HUB_NAME]
        hub_collect[client_name] = ModbusHub(client)

    def stop_modbus(event: Any) -> None:
        """Stop Modbus service."""
        for client in hub_collect.values():
            client.close()

    def start_modbus(event: Any) -> None:
        """Start Modbus service."""
        for client in hub_collect.values():
            client.connect()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

        # Register services for modbus
        hass.services.register(
            DOMAIN,
            SERVICE_WRITE_REGISTER,
            write_register,
            schema=SERVICE_WRITE_REGISTER_SCHEMA,
        )
        hass.services.register(
            DOMAIN,
            SERVICE_WRITE_COIL,
            write_coil,
            schema=SERVICE_WRITE_COIL_SCHEMA)

    def write_register(service: Any) -> None:
        """Write modbus registers."""
        unit = int(float(service.data.get(ATTR_UNIT)))
        address = int(float(service.data.get(ATTR_ADDRESS)))
        value = service.data.get(ATTR_VALUE)
        client_name = service.data.get(CONF_HUB_NAME)
        if isinstance(value, list):
            hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value])
        else:
            hub_collect[client_name].write_register(unit, address,
                                                    int(float(value)))

    def write_coil(service: Any) -> None:
        """Write modbus coil."""
        unit = service.data.get(ATTR_UNIT)
        address = service.data.get(ATTR_ADDRESS)
        state = service.data.get(ATTR_STATE)
        client_name = service.data.get(CONF_HUB_NAME)
        hub_collect[client_name].write_coil(unit, address, state)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_modbus)

    return True


class ModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, modbus_client: "BaseModbusClient") -> None:
        """Initialize the modbus hub."""
        self._client = modbus_client
        self._lock = threading.Lock()

    def close(self) -> None:
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def connect(self) -> None:
        """Connect client."""
        with self._lock:
            self._client.connect()

    def read_coils(self, unit: int, address: int, count: int) -> Any:
        """Read coils."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_coils(address, count, **kwargs)

    def read_input_registers(self, unit: int, address: int, count: int) -> Any:
        """Read input registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_input_registers(address, count, **kwargs)

    def read_holding_registers(self, unit: int, address: int,
                               count: int) -> Any:
        """Read holding registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_holding_registers(address, count,
                                                       **kwargs)

    def write_coil(self, unit: int, address: int, value: int) -> Any:
        """Write coil."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_coil(address, value, **kwargs)

    def write_register(self, unit: int, address: int, value: int) -> Any:
        """Write register."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_register(address, value, **kwargs)

    def write_registers(self, unit: int, address: int,
                        values: List[int]) -> Any:
        """Write registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_registers(address, values, **kwargs)
