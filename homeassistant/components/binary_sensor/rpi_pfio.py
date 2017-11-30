"""
Support for binary sensor using the PiFace Digital I/O module on a RPi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rpi_pfio/
"""
import logging

import voluptuous as vol

import homeassistant.components.rpi_pfio as rpi_pfio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
ATTR_INVERT_LOGIC = 'invert_logic'
ATTR_SETTLE_TIME = 'settle_time'
CONF_PORTS = 'ports'

DEFAULT_INVERT_LOGIC = False
DEFAULT_SETTLE_TIME = 20

DEPENDENCIES = ['rpi_pfio']

PORT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME, default=None): cv.string,
    vol.Optional(ATTR_SETTLE_TIME, default=DEFAULT_SETTLE_TIME):
        cv.positive_int,
    vol.Optional(ATTR_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORTS, default={}): vol.Schema({
        cv.positive_int: PORT_SCHEMA
    })
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the PiFace Digital Input devices."""
    binary_sensors = []
    ports = config.get('ports')
    for port, port_entity in ports.items():
        name = port_entity[ATTR_NAME]
        settle_time = port_entity[ATTR_SETTLE_TIME] / 1000
        invert_logic = port_entity[ATTR_INVERT_LOGIC]

        binary_sensors.append(RPiPFIOBinarySensor(
            hass, port, name, settle_time, invert_logic))
    add_devices(binary_sensors, True)

    rpi_pfio.activate_listener(hass)


class RPiPFIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that a PiFace Digital Input."""

    def __init__(self, hass, port, name, settle_time, invert_logic):
        """Initialize the RPi binary sensor."""
        self._port = port
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._state = None

        def read_pfio(port):
            """Read state from PFIO."""
            self._state = rpi_pfio.read_input(self._port)
            self.schedule_update_ha_state()

        rpi_pfio.edge_detect(hass, self._port, read_pfio, settle_time)

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
        """Update the PFIO state."""
        self._state = rpi_pfio.read_input(self._port)
