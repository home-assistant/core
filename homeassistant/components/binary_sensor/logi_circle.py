"""
This component provides HA binary sensor support for Logi Circle cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.logi_circle/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.logi_circle import parse_logi_activity
from homeassistant.components.logi_circle.const import (
    CONF_ATTRIBUTION, DEVICE_BRAND, DOMAIN as LOGI_CIRCLE_DOMAIN,
    LOGI_BINARY_SENSORS as BINARY_SENSOR_TYPES, SIGNAL_LOGI_CIRCLE_UPDATE)
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_BINARY_SENSORS, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['logi_circle']

_LOGGER = logging.getLogger(__name__)

LOGI_ACTIVITY_PROP = 'activity'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle sensor based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras

    binary_sensors = []
    for sensor_type in (entry.data.get(CONF_BINARY_SENSORS)
                        .get(CONF_MONITORED_CONDITIONS)):
        for binary_sensor in devices:
            if binary_sensor.supports_feature(sensor_type):
                binary_sensors.append(
                    LogiBinarySensor(binary_sensor, sensor_type))

    async_add_entities(binary_sensors, True)


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
        self._activity = {}
        self._async_unsub_dispatcher_connect = None

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
        if (self._sensor_type == 'charging' and
                self._state is not None):
            return 'mdi:battery-charging' if self._state else 'mdi:battery'
        if (self._sensor_type == 'recording' and
                self._state is not None):
            return 'mdi:eye' if self._state else 'mdi:eye-off'
        if (self._sensor_type == 'streaming' and
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
    def device_info(self):
        """Return information about the device."""
        return {
            'name': self._camera.name,
            'identifiers': {
                (LOGI_CIRCLE_DOMAIN, self._camera.id)
            },
            'model': '{} ({})'.format(self._camera.mount, self._camera.model),
            'sw_version': self._camera.firmware,
            'manufacturer': DEVICE_BRAND
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }
        if self._sensor_type == LOGI_ACTIVITY_PROP:
            return {**state, **self._activity}
        return state

    async def async_added_to_hass(self):
        """Register update signal handler."""
        async def async_update_state():
            """Update device state."""
            await self.async_update_ha_state(True)

        self._async_unsub_dispatcher_connect = (
            async_dispatcher_connect(self.hass, SIGNAL_LOGI_CIRCLE_UPDATE,
                                     async_update_state))

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug(
            "Processing data from %s binary sensor (push)", self._name)
        if self._sensor_type == LOGI_ACTIVITY_PROP:
            activity = self._camera.current_activity
            self._state = activity is not None
            self._activity = parse_logi_activity(activity)
        else:
            state = getattr(self._camera, self._sensor_type, None)
            self._state = state
