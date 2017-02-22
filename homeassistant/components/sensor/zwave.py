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

_LOGGER = logging.getLogger(__name__)


FIBARO = 0x010f
FIBARO_MOTION_FGMS001 = 0x1001
FIBARO_MOTION_FGMS001_SENSOR = (FIBARO, FIBARO_MOTION_FGMS001, 0)

WORKAROUND_AG_2_3 = 'association_group_2_3'

DEVICE_MAPPINGS = {
    # The Fibaro motion sensor requires associating to group 2 and 3 to
    # receive the desired reports
    FIBARO_MOTION_FGMS001_SENSOR: WORKAROUND_AG_2_3,
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Z-Wave sensors."""
    # Return on empty `discovery_info`. Given you configure HA with:
    #
    # sensor:
    #   platform: zwave
    #
    # `setup_platform` will be called without `discovery_info`.
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    value.set_change_verified(False)

    # if 1 in groups and (NETWORK.controller.node_id not in
    #                     groups[1].associations):
    #     node.groups[1].add_association(NETWORK.controller.node_id)

    # Make sure that we have values for the key before converting to int
    if (value.node.manufacturer_id.strip() and
            value.node.product_id.strip()):
        specific_sensor_key = (int(value.node.manufacturer_id, 16),
                               int(value.node.product_id, 16),
                               value.index)

        # Check workaround mappings for specific devices.
        if specific_sensor_key in DEVICE_MAPPINGS:
            if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_AG_2_3:
                for group in [2, 3]:
                    if (zwave.NETWORK.controller.node_id not in
                            node.groups[group].associations):
                        node.groups[group].add_association(
                            zwave.NETWORK.controller.node_id)

    # Generic Device mappings
    if node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL):
        add_devices([ZWaveMultilevelSensor(value)])

    elif node.has_command_class(zwave.const.COMMAND_CLASS_METER) and \
            value.type == zwave.const.TYPE_DECIMAL:
        add_devices([ZWaveMultilevelSensor(value)])

    elif node.has_command_class(zwave.const.COMMAND_CLASS_ALARM) or \
            node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_ALARM):
        add_devices([ZWaveAlarmSensor(value)])


class ZWaveSensor(zwave.ZWaveDeviceEntity):
    """Representation of a Z-Wave sensor."""

    def __init__(self, value):
        """Initialize the sensor."""
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Callback on data changes for node values."""
        self._state = self._value.data
        self._units = self._value.units

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
