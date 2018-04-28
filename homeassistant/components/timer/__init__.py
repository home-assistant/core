"""
Timer component.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/timer/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_ENTITY_ID, CONF_ICON, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_utc_time

from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'timer'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

DEFAULT_DURATION = 0
ATTR_DURATION = 'duration'
ATTR_REMAINING = 'remaining'
CONF_DURATION = 'duration'

STATUS_IDLE = 'idle'
STATUS_ACTIVE = 'active'
STATUS_PAUSED = 'paused'

EVENT_TIMER_FINISHED = 'timer.finished'
EVENT_TIMER_CANCELLED = 'timer.cancelled'

SERVICE_START = 'start'
SERVICE_PAUSE = 'pause'
SERVICE_CANCEL = 'cancel'
SERVICE_FINISH = 'finish'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCHEMA_DURATION = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DURATION,
                 default=timedelta(DEFAULT_DURATION)): cv.time_period,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_DURATION, timedelta(DEFAULT_DURATION)):
                cv.time_period,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@bind_hass
def start(hass, entity_id, duration):
    """Start a timer."""
    hass.add_job(async_start, hass, entity_id, {ATTR_ENTITY_ID: entity_id,
                                                ATTR_DURATION: duration})


@callback
@bind_hass
def async_start(hass, entity_id, duration):
    """Start a timer."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_START, {ATTR_ENTITY_ID: entity_id,
                                ATTR_DURATION: duration}))


@bind_hass
def pause(hass, entity_id):
    """Pause a timer."""
    hass.add_job(async_pause, hass, entity_id)


@callback
@bind_hass
def async_pause(hass, entity_id):
    """Pause a timer."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_PAUSE, {ATTR_ENTITY_ID: entity_id}))


@bind_hass
def cancel(hass, entity_id):
    """Cancel a timer."""
    hass.add_job(async_cancel, hass, entity_id)


@callback
@bind_hass
def async_cancel(hass, entity_id):
    """Cancel a timer."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_CANCEL, {ATTR_ENTITY_ID: entity_id}))


@bind_hass
def finish(hass, entity_id):
    """Finish a timer."""
    hass.add_job(async_cancel, hass, entity_id)


@callback
@bind_hass
def async_finish(hass, entity_id):
    """Finish a timer."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_FINISH, {ATTR_ENTITY_ID: entity_id}))


async def async_setup(hass, config):
    """Set up a timer."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        icon = cfg.get(CONF_ICON)
        duration = cfg.get(CONF_DURATION)

        entities.append(Timer(hass, object_id, name, icon, duration))

    if not entities:
        return False

    async def async_handler_service(service):
        """Handle a call to the timer services."""
        target_timers = component.async_extract_from_service(service)

        attr = None
        if service.service == SERVICE_PAUSE:
            attr = 'async_pause'
        elif service.service == SERVICE_CANCEL:
            attr = 'async_cancel'
        elif service.service == SERVICE_FINISH:
            attr = 'async_finish'

        tasks = [getattr(timer, attr)() for timer in target_timers if attr]
        if service.service == SERVICE_START:
            for timer in target_timers:
                tasks.append(
                    timer.async_start(service.data.get(ATTR_DURATION))
                )
        if tasks:
            await asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_START, async_handler_service,
        schema=SERVICE_SCHEMA_DURATION)
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE, async_handler_service,
        schema=SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL, async_handler_service,
        schema=SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_FINISH, async_handler_service,
        schema=SERVICE_SCHEMA)

    await component.async_add_entities(entities)
    return True


class Timer(Entity):
    """Representation of a timer."""

    def __init__(self, hass, object_id, name, icon, duration):
        """Initialize a timer."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._state = STATUS_IDLE
        self._duration = duration
        self._remaining = self._duration
        self._icon = icon
        self._hass = hass
        self._end = None
        self._listener = None

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the timer."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the current value of the timer."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DURATION: str(self._duration),
            ATTR_REMAINING: str(self._remaining)
        }

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        restore_state = self._hass.helpers.restore_state
        state = await restore_state.async_get_last_state(self.entity_id)
        self._state = state and state.state == state

    async def async_start(self, duration):
        """Start a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        newduration = None
        if duration:
            newduration = duration

        self._state = STATUS_ACTIVE
        # pylint: disable=redefined-outer-name
        start = dt_util.utcnow()
        if self._remaining and newduration is None:
            self._end = start + self._remaining
        else:
            if newduration:
                self._duration = newduration
                self._remaining = newduration
            else:
                self._remaining = self._duration
            self._end = start + self._duration
        self._listener = async_track_point_in_utc_time(self._hass,
                                                       self.async_finished,
                                                       self._end)
        await self.async_update_ha_state()

    async def async_pause(self):
        """Pause a timer."""
        if self._listener is None:
            return

        self._listener()
        self._listener = None
        self._remaining = self._end - dt_util.utcnow()
        self._state = STATUS_PAUSED
        self._end = None
        await self.async_update_ha_state()

    async def async_cancel(self):
        """Cancel a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._state = STATUS_IDLE
        self._end = None
        self._remaining = timedelta()
        self._hass.bus.async_fire(EVENT_TIMER_CANCELLED,
                                  {"entity_id": self.entity_id})
        await self.async_update_ha_state()

    async def async_finish(self):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self._hass.bus.async_fire(EVENT_TIMER_FINISHED,
                                  {"entity_id": self.entity_id})
        await self.async_update_ha_state()

    async def async_finished(self, time):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self._hass.bus.async_fire(EVENT_TIMER_FINISHED,
                                  {"entity_id": self.entity_id})
        await self.async_update_ha_state()
