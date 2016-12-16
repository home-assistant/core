"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.sensor import DOMAIN
from homeassistant.components import zwave
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity


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

    # Generic Device mappings
    if node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL):
        add_devices([ZWaveMultilevelSensor(value)])

    elif node.has_command_class(zwave.const.COMMAND_CLASS_METER) and \
            value.type == zwave.const.TYPE_DECIMAL:
        add_devices([ZWaveMultilevelSensor(value)])

    elif node.has_command_class(zwave.const.COMMAND_CLASS_ALARM) or \
            node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_ALARM):
        add_devices([ZWaveAlarmSensor(value)])


class ZWaveSensor(zwave.ZWaveDeviceEntity, Entity):
    """Representation of a Z-Wave sensor."""

    def __init__(self, sensor_value):
        """Initialize the sensor."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        zwave.ZWaveDeviceEntity.__init__(self, sensor_value, DOMAIN)

        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value.data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._value.units

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_ha_state()


class ZWaveMultilevelSensor(ZWaveSensor):
    """Representation of a multi level sensor Z-Wave sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self._value.data

        if self._value.units in ('C', 'F'):
            return round(value, 1)
        elif isinstance(value, float):
            return round(value, 2)

        return value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        unit = self._value.units

        if unit == 'C':
            return TEMP_CELSIUS
        elif unit == 'F':
            return TEMP_FAHRENHEIT
        else:
            return unit


class ZWaveAlarmSensor(ZWaveSensor):
    """Representation of a Z-Wave sensor that sends Alarm alerts.

    Examples include certain Multisensors that have motion and vibration
    capabilities. Z-Wave defines various alarm types such as Smoke, Flood,
    Burglar, CarbonMonoxide, etc.

    This wraps these alarms and allows you to use them to trigger things, etc.

    COMMAND_CLASS_ALARM is what we get here.
    """

    pass
