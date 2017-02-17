"""
Sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zha/
"""
import asyncio
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.components import zha
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Zigbee Home Automation sensors."""
    if discovery_info is None:
        return

    sensor = yield from make_sensor(discovery_info)
    yield from async_add_devices([sensor])


@asyncio.coroutine
def make_sensor(discovery_info):
    """Factory function for ZHA sensors."""
    if discovery_info['unit_of_measurement'] == zha.CENTICELSIUS:
        sensor = TemperatureSensor(**discovery_info)
    else:
        sensor = Sensor(**discovery_info)

    clusters = discovery_info['clusters']
    attr = discovery_info['value_attribute']
    if discovery_info['new_join']:
        cluster = clusters[0]
        yield from cluster.bind()
        yield from cluster.configure_reporting(
            attr,
            300,
            600,
            sensor.min_reportable_change,
        )

    return sensor


class Sensor(zha.Entity):
    """Generic ZHA sensor."""

    _domain = DOMAIN
    min_reportable_change = 1

    def __init__(self, unit_of_measurement, value_attribute, **kwargs):
        """Initialize ZHA sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._value_attribute = value_attribute
        super().__init__(**kwargs)

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        _LOGGER.debug("Attribute updated: %s %s %s", self, attribute, value)
        if attribute == self._value_attribute:
            self._state = value
            self.schedule_update_ha_state()


class TemperatureSensor(Sensor):
    """ZHA temperature sensor."""

    min_reportable_change = 50  # 0.5'C

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entityy."""
        return self.hass.config.units.temperature_unit

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state == 'unknown':
            return 'unknown'
        celsius = round(float(self._state) / 100, 1)
        return convert_temperature(celsius, TEMP_CELSIUS,
                                   self.unit_of_measurement)
