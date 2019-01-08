"""
This component provides HA sensor support for Logi Circle cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.logi_circle/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)
from homeassistant.components.logi_circle import (
    SIGNAL_LOGI_CIRCLE_UPDATE, CONF_ATTRIBUTION, DOMAIN as LOGI_CIRCLE_DOMAIN)
from homeassistant.components.logi_circle.const import (
    POLL_PROPS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_BATTERY_CHARGING,
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,
    STATE_ON, STATE_OFF)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.dt import as_local

DEPENDENCIES = ['logi_circle']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)

# Sensor types: Name, unit of measure, icon per sensor key.
SENSOR_TYPES = {
    'battery_level': [
        'Battery', '%', 'battery-50'],

    'last_activity_time': [
        'Last Activity', None, 'history'],

    'signal_strength_category': [
        'WiFi Signal Category', None, 'wifi'],

    'signal_strength_percentage': [
        'WiFi Signal Strength', '%', 'wifi'],

    'speaker_volume': [
        'Volume', '%', 'volume-high'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=LOGI_CIRCLE_DOMAIN):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle sensor based on a config entry."""

    raw_cameras = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    time_zone = str(hass.config.time_zone)

    cameras = []
    for sensor_type in SENSOR_TYPES:
        for raw_camera in raw_cameras:
            if raw_camera.supports_feature(sensor_type):
                cameras.append(LogiSensor(raw_camera, time_zone, sensor_type))

    async_add_entities(cameras, True)


class LogiSensor(Entity):
    """A sensor implementation for a Logi Circle camera."""

    def __init__(self, camera, time_zone, sensor_type):
        """Initialize a sensor for Logi Circle camera."""
        self._sensor_type = sensor_type
        self._camera = camera
        self._id = '{}-{}'.format(self._camera.id, self._sensor_type)
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])
        self._name = "{0} {1}".format(
            self._camera.name, SENSOR_TYPES.get(self._sensor_type)[0])
        self._state = None
        self._tz = time_zone

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Only poll properties not pushed by WS API."""
        return self._sensor_type in POLL_PROPS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'battery_saving_mode': (
                STATE_ON if self._camera.battery_saving else STATE_OFF),
            'microphone_gain': self._camera.microphone_gain
        }

        if self._sensor_type == 'battery_level':
            state[ATTR_BATTERY_CHARGING] = self._camera.is_charging

        return state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if (self._sensor_type == 'battery_level' and
                self._state is not None):
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

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

        if self._sensor_type == 'last_activity_time':
            activity = self._camera.current_activity or await self._camera.last_activity
            if activity is not None:
                last_activity_time = as_local(activity.end_time_utc)
                self._state = '{0:0>2}:{1:0>2}'.format(
                    last_activity_time.hour, last_activity_time.minute)
        else:
            state = getattr(self._camera, self._sensor_type, None)
            self._state = state
