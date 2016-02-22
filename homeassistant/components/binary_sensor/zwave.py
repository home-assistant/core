"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/binary_sensor.zwave/
"""
import logging

from homeassistant.components.zwave import (
    ATTR_NODE_ID, ATTR_VALUE_ID,
    COMMAND_CLASS_SENSOR_BINARY, NETWORK,
    ZWaveDeviceEntity)
from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Z-Wave platform for sensors."""

    if discovery_info is None or NETWORK is None:
        return

    node = NETWORK.nodes[discovery_info[ATTR_NODE_ID]]
    value = node.values[discovery_info[ATTR_VALUE_ID]]

    value.set_change_verified(False)
    if value.command_class == COMMAND_CLASS_SENSOR_BINARY:
        add_devices([ZWaveBinarySensor(value, "opening")])


class ZWaveBinarySensor(BinarySensorDevice, ZWaveDeviceEntity):
    """Represents a binary sensor within Z-Wave."""

    def __init__(self, value, sensor_class):
        self._sensor_type = sensor_class
        # pylint: disable=import-error
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        ZWaveDeviceEntity.__init__(self, value, DOMAIN)

        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._value.data

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            self.update_ha_state()
