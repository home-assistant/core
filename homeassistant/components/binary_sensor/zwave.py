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


def get_device(values, **kwargs):
    """Create Z-Wave entity device."""
    device_mapping = workaround.get_device_mapping(values.primary)
    if device_mapping == workaround.WORKAROUND_NO_OFF_EVENT:
        # Default the multiplier to 4
        re_arm_multiplier = zwave.get_config_value(values.primary.node, 9) or 4
        return ZWaveTriggerSensor(values, "motion", re_arm_multiplier * 8)

    if workaround.get_device_component_mapping(values.primary) == DOMAIN:
        return ZWaveBinarySensor(values, None)

    if values.primary.command_class == zwave.const.COMMAND_CLASS_SENSOR_BINARY:
        return ZWaveBinarySensor(values, None)
    return None


class ZWaveBinarySensor(BinarySensorDevice, zwave.ZWaveDeviceEntity):
    """Representation of a binary sensor within Z-Wave."""

    def __init__(self, values, device_class):
        """Initialize the sensor."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._sensor_type = device_class
        self._state = self.values.primary.data

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._sensor_type


class ZWaveTriggerSensor(ZWaveBinarySensor):
    """Representation of a stateless sensor within Z-Wave."""

    def __init__(self, values, device_class, re_arm_sec=60):
        """Initialize the sensor."""
        super(ZWaveTriggerSensor, self).__init__(values, device_class)
        self.re_arm_sec = re_arm_sec
        self.invalidate_after = None

    def update_properties(self):
        """Handle value changes for this entity's node."""
        self._state = self.values.primary.data
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
        """Return true if movement has happened within the rearm time."""
        return self._state and \
            (self.invalidate_after is None or
             self.invalidate_after > dt_util.utcnow())
