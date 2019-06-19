"""Support for binary sensor using the PiFace Digital I/O module on a RPi."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.components import rpi_pfio2
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INVERT_LOGIC = 'invert_logic'
CONF_PORTS = 'ports'
CONF_SETTLE_TIME = 'settle_time'

CONF_BOARDS = 'boards'

DEFAULT_INVERT_LOGIC = False
DEFAULT_SETTLE_TIME = 20

DEPENDENCIES = ['rpi_pfio2']

PORT_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SETTLE_TIME, default=DEFAULT_SETTLE_TIME):
        cv.positive_int,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})

BOARD_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORTS, default={}): vol.Schema({
        cv.positive_int: PORT_SCHEMA,
    })
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BOARDS, default={}): vol.Schema({
        cv.positive_int: BOARD_SCHEMA,
    })
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PiFace Digital Input devices."""
    binary_sensors = []
    boards = config.get(CONF_BOARDS)
    for board, board_entity in boards.items():
        ports = board_entity.get(CONF_PORTS)
        for port, port_entity in ports.items():
            name = port_entity.get(CONF_NAME)
            settle_time = port_entity[CONF_SETTLE_TIME] / 1000
            invert_logic = port_entity[CONF_INVERT_LOGIC]

            binary_sensors.append(RPiPFIOBinarySensor(
                hass, port, name, settle_time, invert_logic, board))
    add_entities(binary_sensors, True)

    rpi_pfio2.activate_listener(hass)


class RPiPFIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that a PiFace Digital Input."""

    def __init__(self, hass, port, name, settle_time, invert_logic, hardware_addr=0):
        """Initialize the RPi binary sensor."""
        self._port = port
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._hardware_addr = hardware_addr
        self._state = None

        def read_pfio(port, hardware_addr=0):
            """Read state from PFIO."""
            self._state = rpi_pfio2.read_input(self._port, self._hardware_addr)
            self.schedule_update_ha_state()
        rpi_pfio2.edge_detect(hass, self._port, read_pfio, settle_time, self._hardware_addr)

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

    @property
    def hardware_addr(self):
        """Return the hardware address."""
        return self._hardware_addr

    def update(self):
        """Update the PFIO state."""
        self._state = rpi_pfio2.read_input(self._port, self._hardware_addr)
