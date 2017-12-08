"""
Component to count within automations.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/counter/
"""
import asyncio
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_ENTITY_ID, CONF_ICON, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

ATTR_INITIAL = 'initial'
ATTR_STEP = 'step'

CONF_INITIAL = 'initial'
CONF_STEP = 'step'

DEFAULT_INITIAL = 0
DEFAULT_STEP = 1
DOMAIN = 'counter'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_DECREMENT = 'decrement'
SERVICE_INCREMENT = 'increment'
SERVICE_RESET = 'reset'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_INITIAL, default=DEFAULT_INITIAL):
                cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


@bind_hass
def increment(hass, entity_id):
    """Increment a counter."""
    hass.add_job(async_increment, hass, entity_id)


@callback
@bind_hass
def async_increment(hass, entity_id):
    """Increment a counter."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_INCREMENT, {ATTR_ENTITY_ID: entity_id}))


@bind_hass
def decrement(hass, entity_id):
    """Decrement a counter."""
    hass.add_job(async_decrement, hass, entity_id)


@callback
@bind_hass
def async_decrement(hass, entity_id):
    """Decrement a counter."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_DECREMENT, {ATTR_ENTITY_ID: entity_id}))


@bind_hass
def reset(hass, entity_id):
    """Reset a counter."""
    hass.add_job(async_reset, hass, entity_id)


@callback
@bind_hass
def async_reset(hass, entity_id):
    """Reset a counter."""
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_RESET, {ATTR_ENTITY_ID: entity_id}))


@asyncio.coroutine
def async_setup(hass, config):
    """Set up a counter."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        initial = cfg.get(CONF_INITIAL)
        step = cfg.get(CONF_STEP)
        icon = cfg.get(CONF_ICON)

        entities.append(Counter(object_id, name, initial, step, icon))

    if not entities:
        return False

    @asyncio.coroutine
    def async_handler_service(service):
        """Handle a call to the counter services."""
        target_counters = component.async_extract_from_service(service)

        if service.service == SERVICE_INCREMENT:
            attr = 'async_increment'
        elif service.service == SERVICE_DECREMENT:
            attr = 'async_decrement'
        elif service.service == SERVICE_RESET:
            attr = 'async_reset'

        tasks = [getattr(counter, attr)() for counter in target_counters]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml')
    )

    hass.services.async_register(
        DOMAIN, SERVICE_INCREMENT, async_handler_service,
        descriptions[SERVICE_INCREMENT], SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_DECREMENT, async_handler_service,
        descriptions[SERVICE_DECREMENT], SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RESET, async_handler_service,
        descriptions[SERVICE_RESET], SERVICE_SCHEMA)

    yield from component.async_add_entities(entities)
    return True


class Counter(Entity):
    """Representation of a counter."""

    def __init__(self, object_id, name, initial, step, icon):
        """Initialize a counter."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._step = step
        self._state = self._initial = initial
        self._icon = icon

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the counter."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the current value of the counter."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_INITIAL: self._initial,
            ATTR_STEP: self._step,
        }

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        state = yield from async_get_last_state(self.hass, self.entity_id)
        self._state = state and state.state == state

    @asyncio.coroutine
    def async_decrement(self):
        """Decrement the counter."""
        self._state -= self._step
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_increment(self):
        """Increment a counter."""
        self._state += self._step
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_reset(self):
        """Reset a counter."""
        self._state = self._initial
        yield from self.async_update_ha_state()
