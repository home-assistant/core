"""
Component to offer a way to store a numeric value as an Integer.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/numeric_integer/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_NAME)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'numeric_integer'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_INITIAL = 'initial'
ATTR_VALUE = 'value'

SERVICE_SET_VALUE = 'set_value'

SERVICE_DEFAULT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

SERVICE_SET_VALUE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): vol.Coerce(int),
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_INITIAL): vol.Coerce(int),
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
        })
    })
}, required=True, extra=vol.ALLOW_EXTRA)

SERVICE_TO_METHOD = {
    SERVICE_SET_VALUE: {
        'method': 'async_set_value',
        'schema': SERVICE_SET_VALUE_SCHEMA},
}


@bind_hass
def set_value(hass, entity_id, value):
    """Set numeric_integer to a value."""
    hass.services.call(DOMAIN, SERVICE_SET_VALUE, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    })


@asyncio.coroutine
def async_setup(hass, config):
    """Set up an Numeric Integer."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        initial = cfg.get(CONF_INITIAL)
        icon = cfg.get(CONF_ICON)
        unit = cfg.get(ATTR_UNIT_OF_MEASUREMENT)
        entities.append(NumericValueInt(object_id, name, initial, icon, unit))

    if not entities:
        return False

    @asyncio.coroutine
    def async_handle_service(service):
        """Handle calls to numeric_integer services."""
        target_inputs = component.async_extract_from_service(service)
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        update_tasks = []
        for target_input in target_inputs:
            yield from getattr(target_input, method['method'])(**params)
            if not target_input.should_poll:
                continue
            update_tasks.append(target_input.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service, data in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN, service, async_handle_service, schema=data['schema'])

    yield from component.async_add_entities(entities)
    return True


class NumericValueInt(Entity):
    """Representation of a Numeric Integer."""

    def __init__(self, object_id, name, initial, icon, unit):
        """Initialize an Numeric Integer."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_value = initial
        self._icon = icon
        self._unit = unit

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the Numeric Integer."""
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

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        if self._current_value is not None:
            return

        state = yield from async_get_last_state(self.hass, self.entity_id)
        value = state and int(state.state)

        if value is not None:
            self._current_value = value

    @asyncio.coroutine
    def async_set_value(self, value):
        """Set new value."""
        num_value = int(value)
        self._current_value = num_value
        yield from self.async_update_ha_state()
