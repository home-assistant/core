"""
Support for Modbus.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/modbus/
"""
import logging

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

NETWORK = None
TYPE = None


def setup(hass, config):
    """Setup Modbus component."""
    # Modbus connection type
    # pylint: disable=global-statement, import-error
    global TYPE
    TYPE = config[DOMAIN][MEDIUM]

    # Connect to Modbus network
    # pylint: disable=global-statement, import-error
    global NETWORK

    if TYPE == "serial":
        from pymodbus.client.sync import ModbusSerialClient as ModbusClient
        NETWORK = ModbusClient(method=config[DOMAIN][METHOD],
                               port=config[DOMAIN][SERIAL_PORT],
                               baudrate=config[DOMAIN][BAUDRATE],
                               stopbits=config[DOMAIN][STOPBITS],
                               bytesize=config[DOMAIN][BYTESIZE],
                               parity=config[DOMAIN][PARITY])
    elif TYPE == "tcp":
        from pymodbus.client.sync import ModbusTcpClient as ModbusClient
        NETWORK = ModbusClient(host=config[DOMAIN][HOST],
                               port=config[DOMAIN][IP_PORT])
    elif TYPE == "udp":
        from pymodbus.client.sync import ModbusUdpClient as ModbusClient
        NETWORK = ModbusClient(host=config[DOMAIN][HOST],
                               port=config[DOMAIN][IP_PORT])
    else:
        return False

    def stop_modbus(event):
        """Stop Modbus service."""
        NETWORK.close()

    def start_modbus(event):
        """Start Modbus service."""
        NETWORK.connect()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_modbus)

    return True
