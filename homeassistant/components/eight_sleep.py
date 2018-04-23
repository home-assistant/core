"""
Support for Eight smart mattress covers and mattresses.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/eight_sleep/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SENSORS, CONF_BINARY_SENSORS,
    ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['pyeight==0.0.8']

_LOGGER = logging.getLogger(__name__)

CONF_PARTNER = 'partner'

DATA_EIGHT = 'eight_sleep'
DEFAULT_PARTNER = False
DOMAIN = 'eight_sleep'

HEAT_ENTITY = 'heat'
USER_ENTITY = 'user'

HEAT_SCAN_INTERVAL = timedelta(seconds=60)
USER_SCAN_INTERVAL = timedelta(seconds=300)

SIGNAL_UPDATE_HEAT = 'eight_heat_update'
SIGNAL_UPDATE_USER = 'eight_user_update'

NAME_MAP = {
    'left_current_sleep': 'Left Sleep Session',
    'left_last_sleep': 'Left Previous Sleep Session',
    'left_bed_state': 'Left Bed State',
    'left_presence': 'Left Bed Presence',
    'left_bed_temp': 'Left Bed Temperature',
    'left_sleep_stage': 'Left Sleep Stage',
    'right_current_sleep': 'Right Sleep Session',
    'right_last_sleep': 'Right Previous Sleep Session',
    'right_bed_state': 'Right Bed State',
    'right_presence': 'Right Bed Presence',
    'right_bed_temp': 'Right Bed Temperature',
    'right_sleep_stage': 'Right Sleep Stage',
    'room_temp': 'Room Temperature',
}

SENSORS = ['current_sleep',
           'last_sleep',
           'bed_state',
           'bed_temp',
           'sleep_stage']

SERVICE_HEAT_SET = 'heat_set'

ATTR_TARGET_HEAT = 'target'
ATTR_HEAT_DURATION = 'duration'

VALID_TARGET_HEAT = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100))
VALID_DURATION = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=28800))

SERVICE_EIGHT_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_TARGET_HEAT: VALID_TARGET_HEAT,
    ATTR_HEAT_DURATION: VALID_DURATION,
    })

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PARTNER, default=DEFAULT_PARTNER): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Eight Sleep component."""
    from pyeight.eight import EightSleep

    conf = config.get(DOMAIN)
    user = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    partner = conf.get(CONF_PARTNER)

    if hass.config.time_zone is None:
        _LOGGER.error('Timezone is not set in Home Assistant.')
        return False

    timezone = hass.config.time_zone

    eight = EightSleep(user, password, timezone, partner, None, hass.loop)

    hass.data[DATA_EIGHT] = eight

    # Authenticate, build sensors
    success = yield from eight.start()
    if not success:
        # Authentication failed, cannot continue
        return False

    @asyncio.coroutine
    def async_update_heat_data(now):
        """Update heat data from eight in HEAT_SCAN_INTERVAL."""
        yield from eight.update_device_data()
        async_dispatcher_send(hass, SIGNAL_UPDATE_HEAT)

        async_track_point_in_utc_time(
            hass, async_update_heat_data, utcnow() + HEAT_SCAN_INTERVAL)

    @asyncio.coroutine
    def async_update_user_data(now):
        """Update user data from eight in USER_SCAN_INTERVAL."""
        yield from eight.update_user_data()
        async_dispatcher_send(hass, SIGNAL_UPDATE_USER)

        async_track_point_in_utc_time(
            hass, async_update_user_data, utcnow() + USER_SCAN_INTERVAL)

    yield from async_update_heat_data(None)
    yield from async_update_user_data(None)

    # Load sub components
    sensors = []
    binary_sensors = []
    if eight.users:
        for user in eight.users:
            obj = eight.users[user]
            for sensor in SENSORS:
                sensors.append('{}_{}'.format(obj.side, sensor))
            binary_sensors.append('{}_presence'.format(obj.side))
        sensors.append('room_temp')
    else:
        # No users, cannot continue
        return False

    hass.async_add_job(discovery.async_load_platform(
        hass, 'sensor', DOMAIN, {
            CONF_SENSORS: sensors,
        }, config))

    hass.async_add_job(discovery.async_load_platform(
        hass, 'binary_sensor', DOMAIN, {
            CONF_BINARY_SENSORS: binary_sensors,
        }, config))

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle eight sleep service calls."""
        params = service.data.copy()

        sensor = params.pop(ATTR_ENTITY_ID, None)
        target = params.pop(ATTR_TARGET_HEAT, None)
        duration = params.pop(ATTR_HEAT_DURATION, 0)

        for sens in sensor:
            side = sens.split('_')[1]
            userid = eight.fetch_userid(side)
            usrobj = eight.users[userid]
            yield from usrobj.set_heating_level(target, duration)

        async_dispatcher_send(hass, SIGNAL_UPDATE_HEAT)

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_HEAT_SET, async_service_handler,
        schema=SERVICE_EIGHT_SCHEMA)

    @asyncio.coroutine
    def stop_eight(event):
        """Handle stopping eight api session."""
        yield from eight.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_eight)

    return True


class EightSleepUserEntity(Entity):
    """The Eight Sleep device entity."""

    def __init__(self, eight):
        """Initialize the data object."""
        self._eight = eight

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_eight_user_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_USER, async_eight_user_update)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False


class EightSleepHeatEntity(Entity):
    """The Eight Sleep device entity."""

    def __init__(self, eight):
        """Initialize the data object."""
        self._eight = eight

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_eight_heat_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_HEAT, async_eight_heat_update)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False
