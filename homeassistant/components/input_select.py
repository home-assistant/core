"""
Component to offer a way to select an option from a list.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_select/
"""
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent


DOMAIN = 'input_select'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = 'initial'
CONF_OPTIONS = 'options'

ATTR_OPTION = 'option'
ATTR_OPTIONS = 'options'

SERVICE_SELECT_OPTION = 'select_option'

SERVICE_SELECT_OPTION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OPTION): cv.string,
})


def _cv_input_select(cfg):
    """Config validation helper for input select (Voluptuous)."""
    options = cfg[CONF_OPTIONS]
    state = cfg.get(CONF_INITIAL, options[0])
    if state not in options:
        raise vol.Invalid('initial state "{}" is not part of the options: {}'
                          .format(state, ','.join(options)))
    return cfg


CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    cv.slug: vol.All({
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_OPTIONS): vol.All(cv.ensure_list, vol.Length(min=1),
                                            [cv.string]),
        vol.Optional(CONF_INITIAL): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
    }, _cv_input_select)}}, required=True, extra=vol.ALLOW_EXTRA)


def select_option(hass, entity_id, option):
    """Set input_select to False."""
    hass.services.call(DOMAIN, SERVICE_SELECT_OPTION, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_OPTION: option,
    })


def setup(hass, config):
    """Setup input select."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        options = cfg.get(CONF_OPTIONS)
        state = cfg.get(CONF_INITIAL, options[0])
        icon = cfg.get(CONF_ICON)
        entities.append(InputSelect(object_id, name, state, options, icon))

    if not entities:
        return False

    def select_option_service(call):
        """Handle a calls to the input select services."""
        target_inputs = component.extract_from_service(call)

        for input_select in target_inputs:
            input_select.select_option(call.data[ATTR_OPTION])

    hass.services.register(DOMAIN, SERVICE_SELECT_OPTION,
                           select_option_service,
                           schema=SERVICE_SELECT_OPTION_SCHEMA)

    component.add_entities(entities)

    return True


class InputSelect(Entity):
    """Representation of a select input."""

    # pylint: disable=too-many-arguments
    def __init__(self, object_id, name, state, options, icon):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_option = state
        self._options = options
        self._icon = icon

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

    def select_option(self, option):
        """Select new option."""
        if option not in self._options:
            _LOGGER.warning('Invalid option: %s (possible options: %s)',
                            option, ', '.join(self._options))
            return
        self._current_option = option
        self.update_ha_state()
