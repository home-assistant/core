"""
Component to offer a way to enter a value into a text box.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_text/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_NAME, CONF_MODE)
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'input_text'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_INITIAL = 'initial'
CONF_MIN = 'min'
CONF_MAX = 'max'

MODE_TEXT = 'text'
MODE_PASSWORD = 'password'

ATTR_VALUE = 'value'
ATTR_MIN = 'min'
ATTR_MAX = 'max'
ATTR_PATTERN = 'pattern'
ATTR_MODE = 'mode'

SERVICE_SET_VALUE = 'set_value'

SERVICE_SET_VALUE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): cv.string,
})


def _cv_input_text(cfg):
    """Configure validation helper for input box (voluptuous)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum > maximum:
        raise vol.Invalid('Max len ({}) is not greater than min len ({})'
                          .format(minimum, maximum))
    state = cfg.get(CONF_INITIAL)
    if state is not None and (len(state) < minimum or len(state) > maximum):
        raise vol.Invalid('Initial value {} length not in range {}-{}'
                          .format(state, minimum, maximum))
    return cfg


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_MIN, default=0): vol.Coerce(int),
            vol.Optional(CONF_MAX, default=100): vol.Coerce(int),
            vol.Optional(CONF_INITIAL, ''): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(ATTR_PATTERN): cv.string,
            vol.Optional(CONF_MODE, default=MODE_TEXT):
                vol.In([MODE_TEXT, MODE_PASSWORD]),
        }, _cv_input_text)
    })
}, required=True, extra=vol.ALLOW_EXTRA)


@bind_hass
def set_value(hass, entity_id, value):
    """Set input_text to value."""
    hass.services.call(DOMAIN, SERVICE_SET_VALUE, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    })


@asyncio.coroutine
def async_setup(hass, config):
    """Set up an input text box."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        minimum = cfg.get(CONF_MIN)
        maximum = cfg.get(CONF_MAX)
        initial = cfg.get(CONF_INITIAL)
        icon = cfg.get(CONF_ICON)
        unit = cfg.get(ATTR_UNIT_OF_MEASUREMENT)
        pattern = cfg.get(ATTR_PATTERN)
        mode = cfg.get(CONF_MODE)

        entities.append(InputText(
            object_id, name, initial, minimum, maximum, icon, unit,
            pattern, mode))

    if not entities:
        return False

    component.async_register_entity_service(
        SERVICE_SET_VALUE, SERVICE_SET_VALUE_SCHEMA,
        'async_set_value'
    )

    yield from component.async_add_entities(entities)
    return True


class InputText(Entity):
    """Represent a text box."""

    def __init__(self, object_id, name, initial, minimum, maximum, icon,
                 unit, pattern, mode):
        """Initialize a text input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_value = initial
        self._minimum = minimum
        self._maximum = maximum
        self._icon = icon
        self._unit = unit
        self._pattern = pattern
        self._mode = mode

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the text input entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_MIN: self._minimum,
            ATTR_MAX: self._maximum,
            ATTR_PATTERN: self._pattern,
            ATTR_MODE: self._mode,
        }

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        if self._current_value is not None:
            return

        state = yield from async_get_last_state(self.hass, self.entity_id)
        value = state and state.state

        # Check against None because value can be 0
        if value is not None and self._minimum <= len(value) <= self._maximum:
            self._current_value = value

    @asyncio.coroutine
    def async_set_value(self, value):
        """Select new value."""
        if len(value) < self._minimum or len(value) > self._maximum:
            _LOGGER.warning("Invalid value: %s (length range %s - %s)",
                            value, self._minimum, self._maximum)
            return
        self._current_value = value
        yield from self.async_update_ha_state()
