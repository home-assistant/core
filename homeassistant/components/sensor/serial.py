"""
Support for reading data from a serial port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.serial/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyserial-asyncio==0.4']

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_PORT = 'serial_port'

DEFAULT_NAME = "Serial Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERIAL_PORT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Serial sensor platform."""
    name = config.get(CONF_NAME)
    port = config.get(CONF_SERIAL_PORT)

    sensor = SerialSensor(name, port)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, sensor.stop_serial_read())
    async_add_devices([sensor], True)


class SerialSensor(Entity):
    """Representation of a Serial sensor."""

    def __init__(self, name, port):
        """Initialize the Serial sensor."""
        self._name = name
        self._state = None
        self._port = port
        self._serial_loop_task = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._serial_loop_task = self.hass.loop.create_task(
            self.serial_read(self._port))

    @asyncio.coroutine
    def serial_read(self, device, **kwargs):
        """Read the data from the port."""
        import serial_asyncio
        reader, _ = yield from serial_asyncio.open_serial_connection(
            url=device, **kwargs)
        while True:
            line = yield from reader.readline()
            self._state = line.decode('utf-8').strip()
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def stop_serial_read(self):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
