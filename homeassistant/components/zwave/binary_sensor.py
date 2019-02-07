"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/binary_sensor.zwave/
"""
import logging
import datetime
import homeassistant.util.dt as dt_util
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import track_point_in_time
from homeassistant.components import zwave
from homeassistant.components.zwave import workaround
from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old method of setting up Z-Wave binary sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave binary sensors from Config Entry."""
    @callback
    def async_add_binary_sensor(binary_sensor):
        """Add Z-Wave  binary sensor."""
        async_add_entities([binary_sensor])

    async_dispatcher_connect(hass, 'zwave_new_binary_sensor',
                             async_add_binary_sensor)


def get_device(values, **kwargs):
    """Create Z-Wave entity device."""
    device_mapping = workaround.get_device_mapping(values.primary)
    if device_mapping == workaround.WORKAROUND_NO_OFF_EVENT:
        return ZWaveTriggerSensor(values, "motion")

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

    def __init__(self, values, device_class):
        """Initialize the sensor."""
        super(ZWaveTriggerSensor, self).__init__(values, device_class)
        # Set default off delay to 60 sec
        self.re_arm_sec = 60
        self.invalidate_after = None

    def update_properties(self):
        """Handle value changes for this entity's node."""
        self._state = self.values.primary.data
        _LOGGER.debug('off_delay=%s', self.values.off_delay)
        # Set re_arm_sec if off_delay is provided from the sensor
        if self.values.off_delay:
            _LOGGER.debug('off_delay.data=%s', self.values.off_delay.data)
            self.re_arm_sec = self.values.off_delay.data * 8
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
