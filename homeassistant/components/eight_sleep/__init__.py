"""Support for Eight smart mattress covers and mattresses."""
from datetime import timedelta
import logging

from pyeight.eight import EightSleep
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_BINARY_SENSORS,
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

CONF_PARTNER = "partner"

DATA_EIGHT = "eight_sleep"
DOMAIN = "eight_sleep"

HEAT_ENTITY = "heat"
USER_ENTITY = "user"

HEAT_SCAN_INTERVAL = timedelta(seconds=60)
USER_SCAN_INTERVAL = timedelta(seconds=300)

SIGNAL_UPDATE_HEAT = "eight_heat_update"
SIGNAL_UPDATE_USER = "eight_user_update"

NAME_MAP = {
    "left_current_sleep": "Left Sleep Session",
    "left_current_sleep_fitness": "Left Sleep Fitness",
    "left_last_sleep": "Left Previous Sleep Session",
    "left_bed_state": "Left Bed State",
    "left_presence": "Left Bed Presence",
    "left_bed_temp": "Left Bed Temperature",
    "left_sleep_stage": "Left Sleep Stage",
    "right_current_sleep": "Right Sleep Session",
    "right_current_sleep_fitness": "Right Sleep Fitness",
    "right_last_sleep": "Right Previous Sleep Session",
    "right_bed_state": "Right Bed State",
    "right_presence": "Right Bed Presence",
    "right_bed_temp": "Right Bed Temperature",
    "right_sleep_stage": "Right Sleep Stage",
    "room_temp": "Room Temperature",
}

SENSORS = [
    "current_sleep",
    "current_sleep_fitness",
    "last_sleep",
    "bed_state",
    "bed_temp",
    "sleep_stage",
]

SERVICE_HEAT_SET = "heat_set"

ATTR_TARGET_HEAT = "target"
ATTR_HEAT_DURATION = "duration"

VALID_TARGET_HEAT = vol.All(vol.Coerce(int), vol.Clamp(min=-100, max=100))
VALID_DURATION = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=28800))

SERVICE_EIGHT_SCHEMA = vol.Schema(
    {
        ATTR_ENTITY_ID: cv.entity_ids,
        ATTR_TARGET_HEAT: VALID_TARGET_HEAT,
        ATTR_HEAT_DURATION: VALID_DURATION,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_PARTNER),
            vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_PARTNER): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Eight Sleep component."""

    conf = config.get(DOMAIN)
    user = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant")
        return False

    timezone = str(hass.config.time_zone)

    eight = EightSleep(user, password, timezone, async_get_clientsession(hass))

    hass.data[DATA_EIGHT] = eight

    # Authenticate, build sensors
    success = await eight.start()
    if not success:
        # Authentication failed, cannot continue
        return False

    async def async_update_heat_data(now):
        """Update heat data from eight in HEAT_SCAN_INTERVAL."""
        await eight.update_device_data()
        async_dispatcher_send(hass, SIGNAL_UPDATE_HEAT)

        async_track_point_in_utc_time(
            hass, async_update_heat_data, utcnow() + HEAT_SCAN_INTERVAL
        )

    async def async_update_user_data(now):
        """Update user data from eight in USER_SCAN_INTERVAL."""
        await eight.update_user_data()
        async_dispatcher_send(hass, SIGNAL_UPDATE_USER)

        async_track_point_in_utc_time(
            hass, async_update_user_data, utcnow() + USER_SCAN_INTERVAL
        )

    await async_update_heat_data(None)
    await async_update_user_data(None)

    # Load sub components
    sensors = []
    binary_sensors = []
    if eight.users:
        for user in eight.users:
            obj = eight.users[user]
            for sensor in SENSORS:
                sensors.append(f"{obj.side}_{sensor}")
            binary_sensors.append(f"{obj.side}_presence")
        sensors.append("room_temp")
    else:
        # No users, cannot continue
        return False

    hass.async_create_task(
        discovery.async_load_platform(
            hass, "sensor", DOMAIN, {CONF_SENSORS: sensors}, config
        )
    )

    hass.async_create_task(
        discovery.async_load_platform(
            hass, "binary_sensor", DOMAIN, {CONF_BINARY_SENSORS: binary_sensors}, config
        )
    )

    async def async_service_handler(service):
        """Handle eight sleep service calls."""
        params = service.data.copy()

        sensor = params.pop(ATTR_ENTITY_ID, None)
        target = params.pop(ATTR_TARGET_HEAT, None)
        duration = params.pop(ATTR_HEAT_DURATION, 0)

        for sens in sensor:
            side = sens.split("_")[1]
            userid = eight.fetch_userid(side)
            usrobj = eight.users[userid]
            await usrobj.set_heating_level(target, duration)

        async_dispatcher_send(hass, SIGNAL_UPDATE_HEAT)

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_HEAT_SET, async_service_handler, schema=SERVICE_EIGHT_SCHEMA
    )

    return True


class EightSleepUserEntity(Entity):
    """The Eight Sleep device entity."""

    def __init__(self, eight):
        """Initialize the data object."""
        self._eight = eight

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_eight_user_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_USER, async_eight_user_update
            )
        )

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False


class EightSleepHeatEntity(Entity):
    """The Eight Sleep device entity."""

    def __init__(self, eight):
        """Initialize the data object."""
        self._eight = eight

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_eight_heat_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_HEAT, async_eight_heat_update
            )
        )

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False
