"""Support for Dyson Pure Cool Link Sensors."""
import logging
import asyncio

from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.dyson import DYSON_DEVICES

from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['dyson']

SENSOR_UNITS = {'filter_life': 'hours'}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dyson Sensors."""
    _LOGGER.info("Creating new Dyson fans")
    devices = []
    # Get Dyson Devices from parent component
    for device in hass.data[DYSON_DEVICES]:
        devices.append(DysonFilterLifeSensor(hass, device))
    add_devices(devices)


class DysonFilterLifeSensor(Entity):
    """Representation of Dyson filter life sensor (in hours)."""

    def __init__(self, hass, device):
        """Create a new Dyson filter life sensor."""
        self.hass = hass
        self._device = device
        self._name = "{} filter life".format(self._device.name)
        self._old_value = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.async_add_job(
            self._device.add_message_listener(self.on_message))

    def on_message(self, message):
        """Called when new messages received from the fan."""
        _LOGGER.debug(
            "Message received for %s device: %s", self.name, message)
        # Prevent refreshing if not needed
        if self._old_value is None or self._old_value != self.state:
            self._old_value = self.state
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return filter life in hours.."""
        if self._device.state:
            return self._device.state.filter_life
        else:
            return STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the dyson sensor name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS['filter_life']
