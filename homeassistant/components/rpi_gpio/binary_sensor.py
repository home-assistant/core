"""Support for binary sensor using RPi GPIO."""
import logging
from enum import Enum

import voluptuous as vol

from homeassistant.components import rpi_gpio
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PORTS = "ports"
CONF_PULL_MODE = "pull_mode"
CONF_DETECT = "detect"

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"
DEFAULT_DETECT = "input"


class DetectConfig:
    """RPi GPIO edge detection configuration."""

    def __init__(self, poll: bool, edge: bool):
        """Initialise configuration options."""

        self.poll = poll
        self.edge = edge


class DetectEnum(Enum):
    """Sensor detection modes for config validation."""

    input = DetectConfig(poll=False, edge=False)
    input_poll = DetectConfig(poll=True, edge=False)
    edge = DetectConfig(poll=True, edge=True)


_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
        vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
        vol.Optional(CONF_DETECT, default=DEFAULT_DETECT): cv.enum(DetectEnum),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    pull_mode = config.get(CONF_PULL_MODE)
    bouncetime = config.get(CONF_BOUNCETIME)
    invert_logic = config.get(CONF_INVERT_LOGIC)
    detect = config.get(CONF_DETECT).value

    binary_sensors = []
    ports = config.get("ports")
    for port_num, port_name in ports.items():
        binary_sensors.append(
            RPiGPIOBinarySensor(
                port_name, port_num, pull_mode, bouncetime, invert_logic, detect
            )
        )
    add_entities(binary_sensors, True)


class RPiGPIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses Raspberry Pi GPIO."""

    def __init__(self, name, port, pull_mode, bouncetime, invert_logic, detect):
        """Initialize the RPi binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._pull_mode = pull_mode
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._detect = detect
        self._state = None

        rpi_gpio.setup_input(self._port, self._pull_mode)

        def read_gpio(port):
            """Edge detection callback."""
            self._state = (
                rpi_gpio.read_input(self._port) ^ self._invert_logic
            ) or self._detect.edge
            self.schedule_update_ha_state()

        if self._detect.edge:
            if self._invert_logic:
                trigger_edge = "FALLING"
            else:
                trigger_edge = "RISING"
        else:
            trigger_edge = "BOTH"

        rpi_gpio.edge_detect(self._port, trigger_edge, read_gpio, self._bouncetime)

    @property
    def should_poll(self):
        """Poll GPIO status if configured."""
        return self._detect.poll

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state

    def update(self):
        """Update the GPIO state."""
        self._state = rpi_gpio.read_input(self._port) ^ self._invert_logic
