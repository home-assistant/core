"""
Component to count within automations.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/counter/
"""
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
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


async def async_setup(hass, config):
    """Set up the counters."""
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

    component.async_register_entity_service(
        SERVICE_INCREMENT, SERVICE_SCHEMA,
        'async_increment')
    component.async_register_entity_service(
        SERVICE_DECREMENT, SERVICE_SCHEMA,
        'async_decrement')
    component.async_register_entity_service(
        SERVICE_RESET, SERVICE_SCHEMA,
        'async_reset')

    await component.async_add_entities(entities)
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

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        state = await async_get_last_state(self.hass, self.entity_id)
        self._state = state and state.state == state

    async def async_decrement(self):
        """Decrement the counter."""
        self._state -= self._step
        await self.async_update_ha_state()

    async def async_increment(self):
        """Increment a counter."""
        self._state += self._step
        await self.async_update_ha_state()

    async def async_reset(self):
        """Reset a counter."""
        self._state = self._initial
        await self.async_update_ha_state()
