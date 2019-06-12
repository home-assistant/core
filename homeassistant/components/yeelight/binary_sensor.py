"""Sensor platform support for yeelight."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from . import DATA_YEELIGHT, DATA_UPDATED

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yeelight sensors."""
    if not discovery_info:
        return

    device = hass.data[DATA_YEELIGHT][discovery_info['host']]

    if device.is_nightlight_supported:
        _LOGGER.debug("Adding nightlight mode sensor for %s", device.name)
        add_entities([YeelightNightlightModeSensor(device)])


class YeelightNightlightModeSensor(BinarySensorDevice):
    """Representation of a Yeelight nightlight mode sensor."""

    def __init__(self, device):
        """Initialize nightlight mode sensor."""
        self._device = device

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass,
            DATA_UPDATED.format(self._device.ipaddr),
            self._schedule_immediate_update
        )

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} nightlight".format(self._device.name)

    @property
    def is_on(self):
        """Return true if nightlight mode is on."""
        return self._device.is_nightlight_enabled
