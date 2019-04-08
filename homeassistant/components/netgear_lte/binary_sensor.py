"""Support for Netgear LTE sensors."""
import logging

from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.exceptions import PlatformNotReady

from . import CONF_MONITORED_CONDITIONS, DATA_KEY
from .lte_entity import LTEEntity
from .sensor_types import BINARY_SENSOR_CLASSES

DEPENDENCIES = ['netgear_lte']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE binary sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    binary_sensor_conf = discovery_info[DOMAIN]
    monitored_conditions = binary_sensor_conf[CONF_MONITORED_CONDITIONS]

    binary_sensors = []
    for sensor_type in monitored_conditions:
        binary_sensors.append(LTEBinarySensor(modem_data, sensor_type))

    async_add_entities(binary_sensors)


class LTEBinarySensor(LTEEntity, BinarySensorDevice):
    """Netgear LTE binary sensor entity."""

    @property
    def state(self):
        """Return the state of the binary sensor."""
        if getattr(self.modem_data.data, self.sensor_type):
            return STATE_ON
        return STATE_OFF

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return BINARY_SENSOR_CLASSES[self.sensor_type]
