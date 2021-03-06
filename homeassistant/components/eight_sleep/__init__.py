"""Support for Eight smart mattress covers and mattresses."""
from datetime import timedelta
import logging

from pyeight.eight import EightSleep
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import CONF_PARTNER, DATA_EIGHT, DEFAULT_PARTNER, DOMAIN

_LOGGER = logging.getLogger(__name__)

HEAT_ENTITY = "heat"
USER_ENTITY = "user"

HEAT_SCAN_INTERVAL = timedelta(seconds=60)
USER_SCAN_INTERVAL = timedelta(seconds=300)

SIGNAL_UPDATE_HEAT = "eight_heat_update"
SIGNAL_UPDATE_USER = "eight_user_update"

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
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PARTNER, default=DEFAULT_PARTNER): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup(hass, config):
    """Set up the Eight Sleep component."""
    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Eight Sleep from a config entry."""

    config = entry.data

    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    partner = config.get(CONF_PARTNER)

    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant")
        return False

    timezone = str(hass.config.time_zone)

    eight = EightSleep(user, password, timezone, partner, None, hass.loop)

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

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
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

    async def stop_eight(event):
        """Handle stopping eight api session."""
        await eight.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_eight)

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
