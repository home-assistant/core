"""
This component provides HA binary sensor support for Logi Circle cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.logi_circle/
"""
import logging

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)
from homeassistant.components.logi_circle import (
    SIGNAL_LOGI_CIRCLE_UPDATE,
    CONF_ATTRIBUTION,
    DOMAIN as LOGI_CIRCLE_DOMAIN)
from homeassistant.components.logi_circle.const import (
    ACTIVITY_PROP,
    ACTIVITY_ID,
    ACTIVITY_RELEVANCE,
    ACTIVITY_START_TIME,
    ACTIVITY_DURATION,
    ACTIVITY_BASE
)

from homeassistant.const import (
    ATTR_ATTRIBUTION, STATE_ON, STATE_OFF)

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)

from homeassistant.util.dt import as_local

DEPENDENCIES = ['logi_circle']

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, device_class, icon
BINARY_SENSOR_TYPES = {
    'streaming_enabled': [
        'Streaming Enabled', None, 'camera'],

    'privacy_mode': [
        'Privacy Mode', None, 'eye'],

    'activity': [
        'Activity', 'motion', 'walk']
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle sensor based on a config entry."""

    raw_cameras = await hass.data[LOGI_CIRCLE_DOMAIN].cameras

    cameras = []
    for sensor_type in BINARY_SENSOR_TYPES:
        for raw_camera in raw_cameras:
            cameras.append(LogiBinarySensor(raw_camera, sensor_type))

    async_add_entities(cameras, True)


class LogiBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Logi Circle device."""

    def __init__(self, camera, sensor_type):
        """Initialize a sensor for Logi Circle device."""
        self._sensor_type = sensor_type
        self._camera = camera
        self._name = "{0} {1}".format(
            self._camera.name, BINARY_SENSOR_TYPES.get(self._sensor_type)[0])
        self._device_class = BINARY_SENSOR_TYPES.get(self._sensor_type)[1]
        self._icon = 'mdi:{}'.format(
            BINARY_SENSOR_TYPES.get(self._sensor_type)[2])
        self._state = None
        self._id = '{}-{}'.format(self._camera.id, self._sensor_type)
        self._activity = ACTIVITY_BASE

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (self._sensor_type == 'privacy_mode' and
                self._state is not None):
            return 'mdi:eye-off' if self._state else 'mdi:eye'
        if (self._sensor_type == 'streaming_enabled' and
                self._state is not None):
            return (
                'mdi:camera' if self._state else 'mdi:camera-off')
        return self._icon

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }
        if self._sensor_type == ACTIVITY_PROP:
            return {**state, **self._activity}
        return state

    async def async_added_to_hass(self):
        """Register update signal handler."""
        async def async_update_state():
            """Update device state."""
            await self.async_update(poll=False)
            await self.async_update_ha_state()

        async_dispatcher_connect(self.hass, SIGNAL_LOGI_CIRCLE_UPDATE,
                                 async_update_state)

    async def async_update(self, poll=True):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor", self._name)
        if poll:
            await self._camera.update()

        if self._sensor_type == ACTIVITY_PROP:
            activity = self._camera.current_activity
            if activity:
                self._state = STATE_ON
                self._activity[ACTIVITY_ID] = activity.activity_id
                self._activity[ACTIVITY_RELEVANCE] = activity.relevance_level
                self._activity[ACTIVITY_START_TIME] = as_local(
                    activity.start_time_utc)
                self._activity[ACTIVITY_DURATION] = activity.duration.total_seconds()
            else:
                self._state = STATE_OFF
                self._activity = ACTIVITY_BASE
        else:
            state = getattr(self._camera, self._sensor_type, None)
            self._state = state
