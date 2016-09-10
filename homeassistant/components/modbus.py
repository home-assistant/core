"""
Support for Modbus.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/modbus/
"""
import logging
import threading

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

DOMAIN = "modbus"

REQUIREMENTS = ['https://github.com/bashwork/pymodbus/archive/'
                'd7fc4f1cc975631e0a9011390e8017f64b612661.zip#pymodbus==1.2.0']

# Type of network
MEDIUM = "type"

# if MEDIUM == "serial"
METHOD = "method"
SERIAL_PORT = "port"
BAUDRATE = "baudrate"
STOPBITS = "stopbits"
BYTESIZE = "bytesize"
PARITY = "parity"

# if MEDIUM == "tcp" or "udp"
HOST = "host"
IP_PORT = "port"

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_REGISTER = "write_register"

ATTR_ADDRESS = "address"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

HUB = None
TYPE = None


def setup(hass, config):
    """Setup Modbus component."""
    # Modbus connection type
    # pylint: disable=global-statement, import-error
    global TYPE
    TYPE = config[DOMAIN][MEDIUM]

    # Connect to Modbus network
    # pylint: disable=global-statement, import-error

    if TYPE == "serial":
        from pymodbus.client.sync import ModbusSerialClient as ModbusClient
        client = ModbusClient(method=config[DOMAIN][METHOD],
                              port=config[DOMAIN][SERIAL_PORT],
                              baudrate=config[DOMAIN][BAUDRATE],
                              stopbits=config[DOMAIN][STOPBITS],
                              bytesize=config[DOMAIN][BYTESIZE],
                              parity=config[DOMAIN][PARITY])
    elif TYPE == "tcp":
        from pymodbus.client.sync import ModbusTcpClient as ModbusClient
        client = ModbusClient(host=config[DOMAIN][HOST],
                              port=config[DOMAIN][IP_PORT])
    elif TYPE == "udp":
        from pymodbus.client.sync import ModbusUdpClient as ModbusClient
        client = ModbusClient(host=config[DOMAIN][HOST],
                              port=config[DOMAIN][IP_PORT])
    else:
        return False

    global HUB
    HUB = ModbusHub(client)

    def stop_modbus(event):
        """Stop Modbus service."""
        HUB.close()

    def start_modbus(event):
        """Start Modbus service."""
        HUB.connect()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

        # Register services for modbus
        hass.services.register(DOMAIN, SERVICE_WRITE_REGISTER, write_register)

    def write_register(service):
        """Write modbus registers."""
        unit = int(float(service.data.get(ATTR_UNIT)))
        address = int(float(service.data.get(ATTR_ADDRESS)))
        value = service.data.get(ATTR_VALUE)
        if isinstance(value, list):
            HUB.write_registers(
                unit,
                address,
                [int(float(i)) for i in value])
        else:
            HUB.write_register(
                unit,
                address,
                int(float(value)))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_modbus)

    return True


class ModbusHub(object):
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, modbus_client):
        """Initialize the modbus hub."""
        self._client = modbus_client
        self._lock = threading.Lock()

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
            return self._client.read_coils(
                address,
                count,
                unit=unit)

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            return self._client.read_holding_registers(
                address,
                count,
                unit=unit)

    def write_coil(self, unit, address, value):
        """Write coil."""
        with self._lock:
            self._client.write_coil(
                address,
                value,
                unit=unit)

    def write_register(self, unit, address, value):
        """Write register."""
        with self._lock:
            self._client.write_register(
                address,
                value,
                unit=unit)

    def write_registers(self, unit, address, values):
        """Write registers."""
        with self._lock:
            self._client.write_registers(
                address,
                values,
                unit=unit)
