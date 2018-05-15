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
    """Set up Zigbee Home Automation sensors."""
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    sensor = yield from make_sensor(discovery_info)
    async_add_devices([sensor], update_before_add=True)


@asyncio.coroutine
def make_sensor(discovery_info):
    """Create ZHA sensors factory."""
    from zigpy.zcl.clusters.measurement import (
        RelativeHumidity, TemperatureMeasurement, PressureMeasurement
    )
    in_clusters = discovery_info['in_clusters']
    if RelativeHumidity.cluster_id in in_clusters:
        sensor = RelativeHumiditySensor(**discovery_info)
    elif TemperatureMeasurement.cluster_id in in_clusters:
        sensor = TemperatureSensor(**discovery_info)
    elif PressureMeasurement.cluster_id in in_clusters:
        sensor = PressureSensor(**discovery_info)
    else:
        sensor = Sensor(**discovery_info)

    if discovery_info['new_join']:
        cluster = list(in_clusters.values())[0]
        yield from cluster.bind()
        yield from cluster.configure_reporting(
            sensor.value_attribute, 300, 600, sensor.min_reportable_change,
        )

    return sensor


class Sensor(zha.Entity):
    """Base ZHA sensor."""

    _domain = DOMAIN
    value_attribute = 0
    min_reportable_change = 1

    @property
    def should_poll(self) -> bool:
        """State gets pushed from device."""
        return False

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        _LOGGER.debug("Attribute updated: %s %s %s", self, attribute, value)
        if attribute == self.value_attribute:
            self._state = value
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        result = await zha.safe_read(
            list(self._in_clusters.values())[0],
            [self.value_attribute]
        )
        self._state = result.get(self.value_attribute, self._state)


class TemperatureSensor(Sensor):
    """ZHA temperature sensor."""

    min_reportable_change = 50  # 0.5'C

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self.hass.config.units.temperature_unit

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return None
        celsius = round(float(self._state) / 100, 1)
        return convert_temperature(
            celsius, TEMP_CELSIUS, self.unit_of_measurement)


class RelativeHumiditySensor(Sensor):
    """ZHA relative humidity sensor."""

    min_reportable_change = 50  # 0.5%

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return '%'

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return None

        return round(float(self._state) / 100, 1)


class PressureSensor(Sensor):
    """ZHA pressure sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return 'hPa'

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return None

        return round(float(self._state))
