"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/binary_sensor.zwave/
"""
import logging
import datetime
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_point_in_time
from homeassistant.helpers.entity import Entity
from homeassistant.components import zwave
from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []

PHILIO = 0x013c
PHILIO_SLIM_SENSOR = 0x0002
PHILIO_SLIM_SENSOR_MOTION = (PHILIO, PHILIO_SLIM_SENSOR, 0)
WENZHOU = 0x0118
WENZHOU_SLIM_SENSOR_MOTION = (WENZHOU, PHILIO_SLIM_SENSOR, 0)

WORKAROUND_NO_OFF_EVENT = 'trigger_no_off_event'

DEVICE_MAPPINGS = {
    PHILIO_SLIM_SENSOR_MOTION: WORKAROUND_NO_OFF_EVENT,
    WENZHOU_SLIM_SENSOR_MOTION: WORKAROUND_NO_OFF_EVENT,
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Z-Wave platform for binary sensors."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]
    value.set_change_verified(False)

    # Make sure that we have values for the key before converting to int
    if (value.node.manufacturer_id.strip() and
            value.node.product_id.strip()):
        specific_sensor_key = (int(value.node.manufacturer_id, 16),
                               int(value.node.product_id, 16),
                               value.index)

        if specific_sensor_key in DEVICE_MAPPINGS:
            if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_NO_OFF_EVENT:
                # Default the multiplier to 4
                re_arm_multiplier = (zwave.get_config_value(value.node,
                                                            9) or 4)
                add_devices([
                    ZWaveTriggerSensor(value, "motion",
                                       hass, re_arm_multiplier * 8)
                ])
                return

    if value.command_class == zwave.const.COMMAND_CLASS_SENSOR_BINARY:
        add_devices([ZWaveBinarySensor(value, None)])


class ZWaveBinarySensor(BinarySensorDevice, zwave.ZWaveDeviceEntity, Entity):
    """Representation of a binary sensor within Z-Wave."""

    def __init__(self, value, sensor_class):
        """Initialize the sensor."""
        self._sensor_type = sensor_class
        # pylint: disable=import-error
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)

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
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_ha_state()


class ZWaveTriggerSensor(ZWaveBinarySensor, Entity):
    """Representation of a stateless sensor within Z-Wave."""

    def __init__(self, sensor_value, sensor_class, hass, re_arm_sec=60):
        """Initialize the sensor."""
        super(ZWaveTriggerSensor, self).__init__(sensor_value, sensor_class)
        self._hass = hass
        self.re_arm_sec = re_arm_sec
        self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
            seconds=self.re_arm_sec)
        # If it's active make sure that we set the timeout tracker
        if sensor_value.data:
            track_point_in_time(
                self._hass, self.update_ha_state,
                self.invalidate_after)

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            self.update_ha_state()
            if value.data:
                # only allow this value to be true for re_arm secs
                self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
                    seconds=self.re_arm_sec)
                track_point_in_time(
                    self._hass, self.update_ha_state,
                    self.invalidate_after)

    @property
    def is_on(self):
        """Return True if movement has happened within the rearm time."""
        return self._value.data and \
            (self.invalidate_after is None or
             self.invalidate_after > dt_util.utcnow())
