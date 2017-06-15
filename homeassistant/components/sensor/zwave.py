"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zwave/
"""
import logging
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.sensor import DOMAIN
from homeassistant.components import zwave
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def get_device(node, values, **kwargs):
    """Create Z-Wave entity device."""
    # Generic Device mappings
    if node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL):
        return ZWaveMultilevelSensor(values)
    if node.has_command_class(zwave.const.COMMAND_CLASS_METER) and \
            values.primary.type == zwave.const.TYPE_DECIMAL:
        return ZWaveMultilevelSensor(values)
    if node.has_command_class(zwave.const.COMMAND_CLASS_ALARM) or \
            node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_ALARM):
        return ZWaveAlarmSensor(values)
    return None


class ZWaveSensor(zwave.ZWaveDeviceEntity):
    """Representation of a Z-Wave sensor."""

    def __init__(self, values):
        """Initialize the sensor."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Handle the data changes for node values."""
        self._state = self.values.primary.data
        self._units = self.values.primary.units

    @property
    def force_update(self):
        """Return force_update."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._units


class ZWaveMultilevelSensor(ZWaveSensor):
    """Representation of a multi level sensor Z-Wave sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._units in ('C', 'F'):
            return round(self._state, 1)
        elif isinstance(self._state, float):
            return round(self._state, 2)

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._units == 'C':
            return TEMP_CELSIUS
        elif self._units == 'F':
            return TEMP_FAHRENHEIT
        else:
            return self._units


class ZWaveAlarmSensor(ZWaveSensor):
    """Representation of a Z-Wave sensor that sends Alarm alerts.

    Examples include certain Multisensors that have motion and vibration
    capabilities. Z-Wave defines various alarm types such as Smoke, Flood,
    Burglar, CarbonMonoxide, etc.

    This wraps these alarms and allows you to use them to trigger things, etc.

    COMMAND_CLASS_ALARM is what we get here.
    """

    pass
