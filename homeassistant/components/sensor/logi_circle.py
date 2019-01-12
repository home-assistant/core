"""
This component provides HA sensor support for Logi Circle cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.logi_circle/
"""
import logging
from datetime import timedelta

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)
from homeassistant.components.logi_circle import (
    SIGNAL_LOGI_CIRCLE_UPDATE, CONF_ATTRIBUTION, DOMAIN as LOGI_CIRCLE_DOMAIN,
    LOGI_SENSORS as SENSOR_TYPES)
from homeassistant.components.logi_circle.const import (
    ACTIVITY_BASE, ACTIVITY_ID, ACTIVITY_DURATION,
    ACTIVITY_RELEVANCE, ACTIVITY_START_TIME, DEVICE_BRAND)
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_SENSORS)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.dt import as_local

DEPENDENCIES = ['logi_circle']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)

LOGI_POLLING_SENSORS = ['battery_level',
                        'signal_strength_category',
                        'signal_strength_percentage']


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle sensor based on a config entry."""

    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    time_zone = str(hass.config.time_zone)

    sensors = []
    for sensor_type in entry.data.get(CONF_SENSORS).get(CONF_MONITORED_CONDITIONS):
        for device in devices:
            if device.supports_feature(sensor_type):
                sensors.append(LogiSensor(device, time_zone, sensor_type))

    async_add_entities(sensors, True)


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
        self._activity = ACTIVITY_BASE.copy()
        self._state = None
        self._tz = time_zone
        self._async_unsub_dispatcher_connect = None

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
        return self._sensor_type in LOGI_POLLING_SENSORS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }
        if self._sensor_type == 'last_activity_time':
            return {**state, **self._activity}
        return state

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

        self._async_unsub_dispatcher_connect = (
            async_dispatcher_connect(self.hass, SIGNAL_LOGI_CIRCLE_UPDATE,
                                     async_update_state))

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self, poll=True):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor", self._name)
        if poll and self.should_poll:
            await self._camera.update()

        if self._sensor_type == 'last_activity_time':
            activity = self._camera.current_activity or await self._camera.get_last_activity()
            if activity is not None:
                last_activity_time = as_local(activity.end_time_utc)
                self._state = '{0:0>2}:{1:0>2}'.format(
                    last_activity_time.hour, last_activity_time.minute)
                self._activity[ACTIVITY_ID] = activity.activity_id
                self._activity[ACTIVITY_RELEVANCE] = activity.relevance_level
                self._activity[ACTIVITY_START_TIME] = as_local(
                    activity.start_time_utc)
                self._activity[ACTIVITY_DURATION] = activity.duration.total_seconds()
        else:
            state = getattr(self._camera, self._sensor_type, None)
            self._state = state
