"""Support for Timers."""
from datetime import timedelta
import logging
import typing

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "timer"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

DEFAULT_DURATION = timedelta(0)
ATTR_DURATION = "duration"
ATTR_REMAINING = "remaining"
CONF_DURATION = "duration"

STATUS_IDLE = "idle"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"

EVENT_TIMER_FINISHED = "timer.finished"
EVENT_TIMER_CANCELLED = "timer.cancelled"
EVENT_TIMER_STARTED = "timer.started"
EVENT_TIMER_RESTARTED = "timer.restarted"
EVENT_TIMER_PAUSED = "timer.paused"

SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_CANCEL = "cancel"
SERVICE_FINISH = "finish"


def _none_to_empty_dict(value):
    if value is None:
        return {}
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                _none_to_empty_dict,
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(
                        CONF_DURATION, default=DEFAULT_DURATION
                    ): cv.time_period,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass, config):
    """Set up a timer."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = [
        Timer.from_yaml({CONF_ID: id_, **cfg}) for id_, cfg in config[DOMAIN].items()
    ]

    async def reload_service_handler(service_call):
        """Remove all input booleans and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        new_entities = [
            Timer.from_yaml({CONF_ID: id_, **cfg}) for id_, cfg in conf[DOMAIN].items()
        ]
        if new_entities:
            await component.async_add_entities(new_entities)

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )
    component.async_register_entity_service(
        SERVICE_START,
        {vol.Optional(ATTR_DURATION, default=DEFAULT_DURATION): cv.time_period},
        "async_start",
    )
    component.async_register_entity_service(SERVICE_PAUSE, {}, "async_pause")
    component.async_register_entity_service(SERVICE_CANCEL, {}, "async_cancel")
    component.async_register_entity_service(SERVICE_FINISH, {}, "async_finish")

    if entities:
        await component.async_add_entities(entities)
    return True


class Timer(RestoreEntity):
    """Representation of a timer."""

    def __init__(self, config: typing.Dict):
        """Initialize a timer."""
        self._config = config
        self.editable = True
        self._state = STATUS_IDLE
        self._remaining = config[CONF_DURATION]
        self._end = None
        self._listener = None

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> "Timer":
        """Return entity instance initialized from yaml storage."""
        timer = cls(config)
        timer.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        timer.editable = False
        return timer

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the timer."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self):
        """Return the current value of the timer."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DURATION: str(self._config[CONF_DURATION]),
            ATTR_EDITABLE: self.editable,
            ATTR_REMAINING: str(self._remaining),
        }

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        state = await self.async_get_last_state()
        self._state = state and state.state == state

    async def async_start(self, duration):
        """Start a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        newduration = None
        if duration:
            newduration = duration

        event = EVENT_TIMER_STARTED
        if self._state == STATUS_ACTIVE or self._state == STATUS_PAUSED:
            event = EVENT_TIMER_RESTARTED

        self._state = STATUS_ACTIVE
        start = dt_util.utcnow().replace(microsecond=0)
        if self._remaining and newduration is None:
            self._end = start + self._remaining
        else:
            if newduration:
                self._config[CONF_DURATION] = newduration
                self._remaining = newduration
            else:
                self._remaining = self._config[CONF_DURATION]
            self._end = start + self._config[CONF_DURATION]

        self.hass.bus.async_fire(event, {"entity_id": self.entity_id})

        self._listener = async_track_point_in_utc_time(
            self.hass, self.async_finished, self._end
        )
        await self.async_update_ha_state()

    async def async_pause(self):
        """Pause a timer."""
        if self._listener is None:
            return

        self._listener()
        self._listener = None
        self._remaining = self._end - dt_util.utcnow().replace(microsecond=0)
        self._state = STATUS_PAUSED
        self._end = None
        self.hass.bus.async_fire(EVENT_TIMER_PAUSED, {"entity_id": self.entity_id})
        await self.async_update_ha_state()

    async def async_cancel(self):
        """Cancel a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._state = STATUS_IDLE
        self._end = None
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_CANCELLED, {"entity_id": self.entity_id})
        await self.async_update_ha_state()

    async def async_finish(self):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_FINISHED, {"entity_id": self.entity_id})
        await self.async_update_ha_state()

    async def async_finished(self, time):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_FINISHED, {"entity_id": self.entity_id})
        await self.async_update_ha_state()
