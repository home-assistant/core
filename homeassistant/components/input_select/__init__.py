"""Support to select an option from a list."""
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity

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
    DOMAIN: cv.schema_with_slug_keys(
        vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_OPTIONS):
                vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
            vol.Optional(CONF_INITIAL): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
        }, _cv_input_select)
    )
}, required=True, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
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

    component.async_register_entity_service(
        SERVICE_SELECT_OPTION, SERVICE_SELECT_OPTION_SCHEMA,
        'async_select_option'
    )

    component.async_register_entity_service(
        SERVICE_SELECT_NEXT, SERVICE_SELECT_NEXT_SCHEMA,
        lambda entity, call: entity.async_offset_index(1)
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS, SERVICE_SELECT_PREVIOUS_SCHEMA,
        lambda entity, call: entity.async_offset_index(-1)
    )

    component.async_register_entity_service(
        SERVICE_SET_OPTIONS, SERVICE_SET_OPTIONS_SCHEMA,
        'async_set_options'
    )

    await component.async_add_entities(entities)
    return True


class InputSelect(RestoreEntity):
    """Representation of a select input."""

    def __init__(self, object_id, name, initial, options, icon):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_option = initial
        self._options = options
        self._icon = icon

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self._current_option is not None:
            return

        state = await self.async_get_last_state()
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

    async def async_select_option(self, option):
        """Select new option."""
        if option not in self._options:
            _LOGGER.warning('Invalid option: %s (possible options: %s)',
                            option, ', '.join(self._options))
            return
        self._current_option = option
        await self.async_update_ha_state()

    async def async_offset_index(self, offset):
        """Offset current index."""
        current_index = self._options.index(self._current_option)
        new_index = (current_index + offset) % len(self._options)
        self._current_option = self._options[new_index]
        await self.async_update_ha_state()

    async def async_set_options(self, options):
        """Set options."""
        self._current_option = options[0]
        self._options = options
        await self.async_update_ha_state()
