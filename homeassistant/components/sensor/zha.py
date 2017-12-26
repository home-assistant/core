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
    async_add_devices([sensor])


@asyncio.coroutine
def make_sensor(discovery_info):
    """Create ZHA sensors factory."""
    from bellows.zigbee.zcl.clusters.measurement import TemperatureMeasurement
    from bellows.zigbee.zcl.clusters.measurement import IlluminanceMeasurement
    from bellows.zigbee.zcl.clusters.measurement import RelativeHumidity
    from bellows.zigbee.zcl.clusters.general import PowerConfiguration
    from bellows.zigbee.zcl.clusters.smartenergy import Metering

    in_clusters = discovery_info['in_clusters']

    if TemperatureMeasurement.cluster_id in in_clusters:
        sensor = TemperatureSensor(**discovery_info)
    elif PowerConfiguration.cluster_id in in_clusters \
            and discovery_info['manufacturer'] == 'CentraLite':
        sensor = CentraliteBatterySensor(**discovery_info)
    elif Metering.cluster_id in in_clusters:
        sensor = MeteringSensor(**discovery_info)
    elif IlluminanceMeasurement.cluster_id in in_clusters:
        sensor = IlluminanceMeasurementSensor(**discovery_info)
    elif RelativeHumidity.cluster_id in in_clusters:
        sensor = RelativeHumiditySensor(**discovery_info)
    else:
        sensor = Sensor(**discovery_info)

    attr = sensor.value_attribute

    if discovery_info['new_join']:
        cluster = list(in_clusters.values())[0]
        yield from cluster.bind()
        yield from cluster.configure_reporting(
            attr, 300, 600, sensor.min_reportable_change,
        )

    return sensor


class Sensor(zha.Entity):
    """Base ZHA sensor."""

    _domain = DOMAIN
    value_attribute = 0
    min_reportable_change = 1

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
            self.schedule_update_ha_state()


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
        if self._state == 'unknown':
            return 'unknown'
        celsius = round(float(self._state) / 100, 1)
        return convert_temperature(
            celsius, TEMP_CELSIUS, self.unit_of_measurement)


class CentraliteBatterySensor(Sensor):
    """ZHA battery sensor."""

    #currently restricted to centralite sensors because the value
    #conversion is specific to centralite sensors.

    value_attribute = 32
    minVolts = 15
    maxVolts = 28
    values = {
        28: 100,
        27: 100,
        26: 100,
        25: 90,
        24: 90,
        23: 70,
        22: 70,
        21: 50,
        20: 50,
        19: 30,
        18: 30,
        17: 15,
        16: 1,
        15: 0
    }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return '%'

    @property
    def state(self):
        """Return the state of the entity."""

        if self._state == 'unknown':
            return 'unknown'

        if self._state < self.minVolts:
            self._state = self.minVolts
        elif self._state > self.maxVolts:
            self._state = self.maxVolts

        return self.values.get(self._state, 'unknown')


class MeteringSensor(Sensor):
    """ZHA Metering sensor."""

    value_attribute = 1024

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return 'W'

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state == 'unknown':
            return 'unknown'

        return self._state


class IlluminanceMeasurementSensor(Sensor):
    """ZHA lux sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return 'LUX'

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state == 'unknown':
            return 'unknown'

        return self._state


class RelativeHumiditySensor(Sensor):
    """ZHA humidity sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return '%'
