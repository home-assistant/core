"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/binary_sensor.zwave/
"""
import logging
import datetime
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_point_in_time
from homeassistant.components import zwave
from homeassistant.components.zwave import workaround
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def get_device(value, **kwargs):
    """Create zwave entity device."""
    device_mapping = workaround.get_device_mapping(value)
    if device_mapping == workaround.WORKAROUND_NO_OFF_EVENT:
        # Default the multiplier to 4
        re_arm_multiplier = (zwave.get_config_value(value.node, 9) or 4)
        return ZWaveTriggerSensor(value, "motion", re_arm_multiplier * 8)

    if workaround.get_device_component_mapping(value) == DOMAIN:
        return ZWaveBinarySensor(value, None)

    if value.command_class == zwave.const.COMMAND_CLASS_SENSOR_BINARY:
        return ZWaveBinarySensor(value, None)
    return None


class ZWaveBinarySensor(BinarySensorDevice, zwave.ZWaveDeviceEntity):
    """Representation of a binary sensor within Z-Wave."""

    def __init__(self, value, device_class):
        """Initialize the sensor."""
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._sensor_type = device_class
        self._state = self._value.data

    def update_properties(self):
        """Callback on data changes for node values."""
        self._state = self._value.data

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed."""
        return False


class ZWaveTriggerSensor(ZWaveBinarySensor):
    """Representation of a stateless sensor within Z-Wave."""

    def __init__(self, value, device_class, re_arm_sec=60):
        """Initialize the sensor."""
        super(ZWaveTriggerSensor, self).__init__(value, device_class)
        self.re_arm_sec = re_arm_sec
        self.invalidate_after = None

    def update_properties(self):
        """Called when a value for this entity's node has changed."""
        self._state = self._value.data
        # only allow this value to be true for re_arm secs
        if not self.hass:
            return

        self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
            seconds=self.re_arm_sec)
        track_point_in_time(
            self.hass, self.async_update_ha_state,
            self.invalidate_after)

    @property
    def is_on(self):
        """Return True if movement has happened within the rearm time."""
        return self._state and \
            (self.invalidate_after is None or
             self.invalidate_after > dt_util.utcnow())
