"""
Component to offer a way to select an option from a list.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_select/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'input_select'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_INITIAL = 'initial'
CONF_OPTIONS = 'options'

ATTR_OPTION = 'option'
ATTR_OPTIONS = 'options'

SERVICE_SELECT_OPTION = 'select_option'

SERVICE_SELECT_OPTION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OPTION): cv.string,
})

SERVICE_SELECT_NEXT = 'select_next'

SERVICE_SELECT_NEXT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SELECT_PREVIOUS = 'select_previous'

SERVICE_SELECT_PREVIOUS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


SERVICE_SET_OPTIONS = 'set_options'

SERVICE_SET_OPTIONS_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OPTIONS):
        vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
})


def _cv_input_select(cfg):
    """Configure validation helper for input select (voluptuous)."""
    options = cfg[CONF_OPTIONS]
    initial = cfg.get(CONF_INITIAL)
    if initial is not None and initial not in options:
        raise vol.Invalid('initial state "{}" is not part of the options: {}'
                          .format(initial, ','.join(options)))
    return cfg


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_OPTIONS):
                vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
            vol.Optional(CONF_INITIAL): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
        }, _cv_input_select)})
}, required=True, extra=vol.ALLOW_EXTRA)


@bind_hass
def select_option(hass, entity_id, option):
    """Set value of input_select."""
    hass.services.call(DOMAIN, SERVICE_SELECT_OPTION, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_OPTION: option,
    })


@bind_hass
def select_next(hass, entity_id):
    """Set next value of input_select."""
    hass.services.call(DOMAIN, SERVICE_SELECT_NEXT, {
        ATTR_ENTITY_ID: entity_id,
    })


@bind_hass
def select_previous(hass, entity_id):
    """Set previous value of input_select."""
    hass.services.call(DOMAIN, SERVICE_SELECT_PREVIOUS, {
        ATTR_ENTITY_ID: entity_id,
    })


@bind_hass
def set_options(hass, entity_id, options):
    """Set options of input_select."""
    hass.services.call(DOMAIN, SERVICE_SET_OPTIONS, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_OPTIONS: options,
    })


@asyncio.coroutine
def async_setup(hass, config):
    """Set up an input select."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        options = cfg.get(CONF_OPTIONS)
        initial = cfg.get(CONF_INITIAL)
        icon = cfg.get(CONF_ICON)
        entities.append(InputSelect(object_id, name, initial, options, icon))

    if not entities:
        return False

    @asyncio.coroutine
    def async_select_option_service(call):
        """Handle a calls to the input select option service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = [input_select.async_select_option(call.data[ATTR_OPTION])
                 for input_select in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_OPTION, async_select_option_service,
        schema=SERVICE_SELECT_OPTION_SCHEMA)

    @asyncio.coroutine
    def async_select_next_service(call):
        """Handle a calls to the input select next service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = [input_select.async_offset_index(1)
                 for input_select in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_NEXT, async_select_next_service,
        schema=SERVICE_SELECT_NEXT_SCHEMA)

    @asyncio.coroutine
    def async_select_previous_service(call):
        """Handle a calls to the input select previous service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = [input_select.async_offset_index(-1)
                 for input_select in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_PREVIOUS, async_select_previous_service,
        schema=SERVICE_SELECT_PREVIOUS_SCHEMA)

    @asyncio.coroutine
    def async_set_options_service(call):
        """Handle a calls to the set options service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = [input_select.async_set_options(call.data[ATTR_OPTIONS])
                 for input_select in target_inputs]
        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OPTIONS, async_set_options_service,
        schema=SERVICE_SET_OPTIONS_SCHEMA)

    yield from component.async_add_entities(entities)
    return True


class InputSelect(Entity):
    """Representation of a select input."""

    def __init__(self, object_id, name, initial, options, icon):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_option = initial
        self._options = options
        self._icon = icon

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Run when entity about to be added."""
        if self._current_option is not None:
            return

        state = yield from async_get_last_state(self.hass, self.entity_id)
        if not state or state.state not in self._options:
            self._current_option = self._options[0]
        else:
            self._current_option = state.state

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the select input."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_option

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_OPTIONS: self._options,
        }

    @asyncio.coroutine
    def async_select_option(self, option):
        """Select new option."""
        if option not in self._options:
            _LOGGER.warning('Invalid option: %s (possible options: %s)',
                            option, ', '.join(self._options))
            return
        self._current_option = option
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_offset_index(self, offset):
        """Offset current index."""
        current_index = self._options.index(self._current_option)
        new_index = (current_index + offset) % len(self._options)
        self._current_option = self._options[new_index]
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_options(self, options):
        """Set options."""
        self._current_option = options[0]
        self._options = options
        yield from self.async_update_ha_state()
