"""Support for Modbus."""
import logging
import threading

from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient, ModbusUdpClient
from pymodbus.transaction import ModbusRtuFramer
import voluptuous as vol

from homeassistant.const import (
    ATTR_STATE,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = "address"
ATTR_HUB = "hub"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_HUB = "hub"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"

DEFAULT_HUB = "default"
DOMAIN = "modbus"

SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"

BASE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string})

SERIAL_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_BAUDRATE): cv.positive_int,
        vol.Required(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
        vol.Required(CONF_METHOD): vol.Any("rtu", "ascii"),
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PARITY): vol.Any("E", "O", "N"),
        vol.Required(CONF_STOPBITS): vol.Any(1, 2),
        vol.Required(CONF_TYPE): "serial",
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
    }
)

ETHERNET_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TYPE): vol.Any("tcp", "udp", "rtuovertcp"),
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA)])},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Any(
            cv.positive_int, vol.All(cv.ensure_list, [cv.positive_int])
        ),
    }
)

SERVICE_WRITE_COIL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_STATE): cv.boolean,
    }
)


def setup_client(client_config):
    """Set up pymodbus client."""
    client_type = client_config[CONF_TYPE]

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


def setup(hass, config):
    """Set up Modbus component."""
    hass.data[DOMAIN] = hub_collect = {}

    for client_config in config[DOMAIN]:
        client = setup_client(client_config)
        name = client_config[CONF_NAME]
        hub_collect[name] = ModbusHub(client, name)
        _LOGGER.debug("Setting up hub: %s", client_config)

    def stop_modbus(event):
        """Stop Modbus service."""
        for client in hub_collect.values():
            client.close()

    def start_modbus(event):
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
            DOMAIN, SERVICE_WRITE_COIL, write_coil, schema=SERVICE_WRITE_COIL_SCHEMA
        )

    def write_register(service):
        """Write Modbus registers."""
        unit = int(float(service.data[ATTR_UNIT]))
        address = int(float(service.data[ATTR_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = service.data[ATTR_HUB]
        if isinstance(value, list):
            hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value]
            )
        else:
            hub_collect[client_name].write_register(unit, address, int(float(value)))

    def write_coil(service):
        """Write Modbus coil."""
        unit = service.data[ATTR_UNIT]
        address = service.data[ATTR_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = service.data[ATTR_HUB]
        hub_collect[client_name].write_coil(unit, address, state)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_modbus)

    return True


class ModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, modbus_client, name):
        """Initialize the Modbus hub."""
        self._client = modbus_client
        self._lock = threading.Lock()
        self._name = name

    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def connect(self):
        """Connect client."""
        with self._lock:
            self._client.connect()

    def read_coils(self, unit, address, count):
        """Read coils."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_coils(address, count, **kwargs)

    def read_discrete_inputs(self, unit, address, count):
        """Read discrete inputs."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_discrete_inputs(address, count, **kwargs)

    def read_input_registers(self, unit, address, count):
        """Read input registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_input_registers(address, count, **kwargs)

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_holding_registers(address, count, **kwargs)

    def write_coil(self, unit, address, value):
        """Write coil."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_coil(address, value, **kwargs)

    def write_register(self, unit, address, value):
        """Write register."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_register(address, value, **kwargs)

    def write_registers(self, unit, address, values):
        """Write registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_registers(address, values, **kwargs)
