"""Support for LightwaveRF TRV - Associated Battery."""
import logging

from homeassistant.const import CONF_NAME, DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity

from . import CONF_SERIAL, LIGHTWAVE_LINK

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return battery."""
    if not discovery_info:
        return

    batt = []

    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        serial = device_config[CONF_SERIAL]
        batt.append(LightwaveBattery(name, device_id, lwlink, serial))

    async_add_entities(batt)


class LightwaveBattery(Entity):
    """Lightwave TRV Battery."""

    def __init__(self, name, device_id, lwlink, serial):
        """Initialize the Lightwave Trv battery sensor."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._lwlink = lwlink
        self._serial = serial
        self._device_class = DEVICE_CLASS_BATTERY
        self._unit_of_measurement = "%"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the state of the sensor."""
        return self._unit_of_measurement

    def update(self):
        """Communicate with a Lightwave RTF Proxy to get state."""
        battery = None
        (dummy_temp, dummy_targ, battery, dummy_output) = self._lwlink.read_trv_status(
            self._serial
        )
        self._state = battery
