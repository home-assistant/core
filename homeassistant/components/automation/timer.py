import asyncio
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.const import (ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, CONF_DURATION, STATE_RUNNING, STATE_STOPPED, SERVICE_TIMER_START, SERVICE_TIMER_RESTART, SERVICE_TIMER_CANCEL)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'timer'
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_START_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_DURATION): cv.time_period,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_DURATION): cv.time_period,
            vol.Optional(CONF_ICON): cv.icon,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for binary sensors."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        duration = cfg.get(CONF_DURATION)
        icon = cfg.get(CONF_ICON)

        entities.append(Timer(object_id, name, duration, icon))

    if not entities:
        return False

    @asyncio.coroutine
    def async_timer_start_service(call):
        """Handle a calls to the input select option service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = [timer.async_start(call.data[CONF_DURATION])
                 for timer in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_TIMER_START, async_timer_start_service, schema=SERVICE_START_SCHEMA)

    @asyncio.coroutine
    def async_handler_service(call):
        """Handle a calls to the input boolean services."""
        target_inputs = component.async_extract_from_service(call)

        if call.service == SERVICE_TIMER_RESTART:
            attr = 'async_restart'
        elif call.service == SERVICE_TIMER_CANCEL:
            attr = 'async_cancel'

        tasks = [getattr(input_b, attr)() for input_b in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_TIMER_RESTART, async_handler_service, schema=SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TIMER_CANCEL, async_handler_service, schema=SERVICE_SCHEMA)

    yield from component.async_setup(config)
    return True

class Timer(Entity):
    """Represent a countdown timer."""

    def __init__(self, object_id, name, duration, icon):
        """Initialize a boolean input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._duration = duration
        self._is_running = False
        self._icon = icon

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def is_running(self):
        """Whether the timer is currently running."""
        return self._is_running

    @property
    def state(self):
        """Return the state of the timer."""
        return STATE_RUNNING if self.is_running else STATE_STOPPED

    @asyncio.coroutine
    def async_start(self, duration=None):
        """Turn the entity on."""

        if self._is_running:
            return

        if duration:
            # TODO: Override the duration



        # TODO: Start the timer

        # TODO: Fire start event

        self._is_running = True

        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_restart(self):
        if not self._is_running:
            return

        # TODO: Fire a restart event
        # TODO: Cancel previous timer
        # TODO: Start new timer


    @asyncio.coroutine
    def async_cancel(self):
        if not self._is_running:
            return

        # TODO: Cancel previous timer
        # TODO: Fire cancellation event

        self._is_running = False

        yield from self.async_update_ha_state()

