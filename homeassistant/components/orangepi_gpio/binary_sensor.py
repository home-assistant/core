"""Support for binary sensor using Orange Pi GPIO."""
import logging

from homeassistant.components import orangepi_gpio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME

from . import CONF_PIN_MODE
from .const import CONF_INVERT_LOGIC, CONF_PORTS, PORT_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(PORT_SCHEMA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Orange Pi GPIO devices."""
    pin_mode = config[CONF_PIN_MODE]
    orangepi_gpio.setup_mode(pin_mode)

    invert_logic = config[CONF_INVERT_LOGIC]

    binary_sensors = []
    ports = config[CONF_PORTS]
    for port_num, port_name in ports.items():
        binary_sensors.append(OPiGPIOBinarySensor(
            port_name, port_num, invert_logic))
    add_entities(binary_sensors, True)


class OPiGPIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses Orange Pi GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the Orange Pi binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = None

        orangepi_gpio.setup_input(self._port)

        def read_gpio(port):
            """Read state from GPIO."""
            self._state = orangepi_gpio.read_input(self._port)
            self.schedule_update_ha_state()

        orangepi_gpio.edge_detect(self._port, read_gpio)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    def update(self):
        """Update the GPIO state."""
        self._state = orangepi_gpio.read_input(self._port)
