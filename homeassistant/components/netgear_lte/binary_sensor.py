"""Support for Netgear LTE binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.exceptions import PlatformNotReady

from . import DATA_KEY, LTEEntity
from . import sensor_types

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE binary sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    binary_sensors = []
    for sensor_type in sensor_types.ALL_BINARY_SENSORS:
        binary_sensors.append(LTEBinarySensor(modem_data, sensor_type))

    async_add_entities(binary_sensors)


class LTEBinarySensor(LTEEntity, BinarySensorDevice):
    """Netgear LTE binary sensor entity."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self.modem_data.data, self.sensor_type)

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return sensor_types.BINARY_SENSOR_CLASSES[self.sensor_type]
