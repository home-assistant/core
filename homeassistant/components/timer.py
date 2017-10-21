"""
Timer component.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/timer/
"""
import asyncio
import logging
import os
from datetime import timedelta

import voluptuous as vol

import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_ENTITY_ID, CONF_ICON, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.event import async_track_point_in_utc_time

from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

EVENT_TIMER_STARTED = 'timer.started'
EVENT_TIMER_PAUSED = 'timer.paused'
EVENT_TIMER_FINISHED = 'timer.finished'
EVENT_TIMER_CANCELLED = 'timer.cancelled'

ATTR_STATUS = 'status'
ATTR_DURATION = 'duration'
ATTR_START = 'start'
ATTR_END = 'end'
ATTR_REMAINING = 'remaining'

STATUS_IDLE = 0
STATUS_ACTIVE = 1
STATUS_PAUSED = 2

STATUS_MAPPING = {
    STATUS_IDLE: 'idle',
    STATUS_ACTIVE: 'active',
    STATUS_PAUSED: 'paused'
}

CONF_DURATION = 'duration'

DEFAULT_DURATION = 0
DOMAIN = 'timer'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_START = 'start'
SERVICE_PAUSE = 'pause'
SERVICE_CANCEL = 'cancel'
SERVICE_FINISH = 'finish'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCHEMA_DURATION = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DURATION): cv.positive_int,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_DURATION, default=DEFAULT_DURATION):
                cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@bind_hass
def start(hass, entity_id, duration):
    """Start a timer."""
    hass.add_job(async_start, hass, entity_id, duration)


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
def cancel(hass, entity_id, duration):
    """Cancel a timer."""
    hass.add_job(async_cancel, hass, entity_id)


@callback
@bind_hass
def async_cancel(hass, entity_id, duration):
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


@asyncio.coroutine
def async_setup(hass, config):
    """Set up a timer."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        duration = cfg.get(CONF_DURATION)
        icon = cfg.get(CONF_ICON)

        entities.append(Timer(hass, object_id, name, duration, icon))

    if not entities:
        return False

    @asyncio.coroutine
    def async_handler_service(service):
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
                    timer.async_start(service.data.get(ATTR_DURATION,
                                                       DEFAULT_DURATION)))
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml')
    )

    hass.services.async_register(
        DOMAIN, SERVICE_START, async_handler_service,
        descriptions[DOMAIN][SERVICE_START], SERVICE_SCHEMA_DURATION)
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE, async_handler_service,
        descriptions[DOMAIN][SERVICE_PAUSE], SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL, async_handler_service,
        descriptions[DOMAIN][SERVICE_CANCEL], SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_FINISH, async_handler_service,
        descriptions[DOMAIN][SERVICE_FINISH], SERVICE_SCHEMA)

    yield from component.async_add_entities(entities)
    return True


class Timer(Entity):
    """Representation of a timer."""

    def __init__(self, hass, object_id, name, duration, icon):
        """Initialize a timer."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._state = STATUS_IDLE
        self._duration = duration
        self._remaining = None
        self._icon = icon
        self._hass = hass
        self._start = None
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
            ATTR_DURATION: self._duration,
            ATTR_START: self._start,
            ATTR_END: self._end,
            ATTR_REMAINING: self._remaining
        }

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        state = yield from async_get_last_state(self.hass, self.entity_id)
        self._state = state and state.state == state

    @asyncio.coroutine
    def async_start(self, duration):
        """Start a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._duration = duration if duration else self._duration
        self._state = STATUS_ACTIVE
        self._start = dt_util.utcnow()
        if self._remaining and not duration:
            self._end = self._start + timedelta(seconds=self._remaining)
        else:
            self._end = self._start + timedelta(seconds=self._duration)
        self._listener = async_track_point_in_utc_time(self._hass,
                                                       self.async_finished,
                                                       self._end)
        self._hass.bus.async_fire(EVENT_TIMER_STARTED,
                                  {"entity_id": self.entity_id})
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_pause(self):
        """Pause a timer."""
        if self._listener:
            self._listener()
            self._listener = None
            self._remaining = (self._end - dt_util.utcnow()).seconds
            self._state = STATUS_PAUSED
            self._end = None
            self._hass.bus.async_fire(EVENT_TIMER_PAUSED,
                                      {"entity_id": self.entity_id})
            yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_cancel(self):
        """Cancel a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._state = STATUS_IDLE
        self._start = None
        self._end = None
        self._remaining = None
        self._hass.bus.async_fire(EVENT_TIMER_CANCELLED,
                                  {"entity_id": self.entity_id})
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_finish(self, time):
        """Reset and updates the states, fire finished event."""
        if self._state == STATUS_ACTIVE:
            self._listener = None
            self._state = STATUS_IDLE
            self._remaining = None
            self._hass.bus.async_fire(EVENT_TIMER_FINISHED,
                                      {"entity_id": self.entity_id})
            yield from self.async_update_ha_state()
        return

    @asyncio.coroutine
    def async_finished(self, time):
        """Reset and updates the states, fire finished event."""
        if self._state == STATUS_ACTIVE:
            self._listener = None
            self._state = STATUS_IDLE
            self._remaining = None
            self._hass.bus.async_fire(EVENT_TIMER_FINISHED,
                                      {"entity_id": self.entity_id})
            yield from self.async_update_ha_state()
        return
