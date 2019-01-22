"""
Component to count within automations.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/counter/
"""
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME,\
    CONF_MAXIMUM, CONF_MINIMUM

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

ATTR_INITIAL = 'initial'
ATTR_STEP = 'step'

CONF_INITIAL = 'initial'
CONF_RESTORE = 'restore'
CONF_STEP = 'step'

DEFAULT_INITIAL = 0
DEFAULT_STEP = 1
DOMAIN = 'counter'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_DECREMENT = 'decrement'
SERVICE_INCREMENT = 'increment'
SERVICE_RESET = 'reset'
SERVICE_SETUP = 'setup'

SERVICE_SCHEMA_SIMPLE = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})
SERVICE_SCHEMA_SETUP = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    vol.Optional(CONF_MINIMUM): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_MAXIMUM): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_STEP): cv.positive_int,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Any({
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_INITIAL, default=DEFAULT_INITIAL):
                cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_MAXIMUM, default=None):
                vol.Any(None, vol.Coerce(int)),
            vol.Optional(CONF_MINIMUM, default=None):
                vol.Any(None, vol.Coerce(int)),
            vol.Optional(CONF_RESTORE, default=True): cv.boolean,
            vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
        }, None)
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the counters."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        initial = cfg.get(CONF_INITIAL)
        restore = cfg.get(CONF_RESTORE)
        step = cfg.get(CONF_STEP)
        icon = cfg.get(CONF_ICON)
        minimum = cfg.get(CONF_MINIMUM)
        maximum = cfg.get(CONF_MAXIMUM)

        entities.append(Counter(object_id, name, initial, minimum, maximum,
                                restore, step, icon))

    if not entities:
        return False

    component.async_register_entity_service(
        SERVICE_INCREMENT, SERVICE_SCHEMA_SIMPLE,
        'async_increment')
    component.async_register_entity_service(
        SERVICE_DECREMENT, SERVICE_SCHEMA_SIMPLE,
        'async_decrement')
    component.async_register_entity_service(
        SERVICE_RESET, SERVICE_SCHEMA_SIMPLE,
        'async_reset')
    component.async_register_entity_service(
        SERVICE_SETUP, SERVICE_SCHEMA_SETUP,
        'async_setup')

    await component.async_add_entities(entities)
    return True


class Counter(Entity):
    """Representation of a counter."""

    def __init__(self, object_id, name, initial, minimum, maximum,
                 restore, step, icon):
        """Initialize a counter."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._restore = restore
        self._step = step
        self._state = self._initial = initial
        self._min = minimum
        self._max = maximum
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
        ret = {
            ATTR_INITIAL: self._initial,
            ATTR_STEP: self._step,
        }
        if self._min is not None:
            ret[CONF_MINIMUM] = self._min
        if self._max is not None:
            ret[CONF_MAXIMUM] = self._max
        return ret

    def __check_boundaries(self):
        """Check if in range of min/max values."""
        if self._min is not None:
            self._state = max(self._min, self._state)
        if self._max is not None:
            self._state = min(self._max, self._state)

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        # __init__ will set self._state to self._initial, only override
        # if needed.
        if self._restore:
            state = await async_get_last_state(self.hass, self.entity_id)
            if state is not None:
                self._state = int(state.state)
                self.__check_boundaries()

    async def async_decrement(self):
        """Decrement the counter."""
        self._state -= self._step
        self.__check_boundaries()
        await self.async_update_ha_state()

    async def async_increment(self):
        """Increment a counter."""
        self._state += self._step
        self.__check_boundaries()
        await self.async_update_ha_state()

    async def async_reset(self):
        """Reset a counter."""
        self._state = self._initial
        self.__check_boundaries()
        await self.async_update_ha_state()

    async def async_setup(self, **kwargs):
        """Change the counters settings with a service."""
        if CONF_MINIMUM in kwargs:
            self._min = kwargs[CONF_MINIMUM]
        if CONF_MAXIMUM in kwargs:
            self._max = kwargs[CONF_MAXIMUM]
        if CONF_STEP in kwargs:
            self._step = kwargs[CONF_STEP]

        self.__check_boundaries()
        await self.async_update_ha_state()
