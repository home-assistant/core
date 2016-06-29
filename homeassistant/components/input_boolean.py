"""
Component to keep track of user controlled booleans for within automation.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_boolean/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import slugify

DOMAIN = 'input_boolean'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
CONF_INITIAL = "initial"
CONF_ICON = "icon"

TOGGLE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def is_on(hass, entity_id):
    """Test if input_boolean is True."""
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id):
    """Set input_boolean to True."""
    hass.services.call(DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id})


def turn_off(hass, entity_id):
    """Set input_boolean to False."""
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})


def setup(hass, config):
    """Set up input boolean."""
    if not isinstance(config.get(DOMAIN), dict):
        _LOGGER.error('Expected %s config to be a dictionary', DOMAIN)
        return False

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if object_id != slugify(object_id):
            _LOGGER.warning("Found invalid key for boolean input: %s. "
                            "Use %s instead", object_id, slugify(object_id))
            continue
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        state = cfg.get(CONF_INITIAL, False)
        icon = cfg.get(CONF_ICON)

        entities.append(InputBoolean(object_id, name, state, icon))

    if not entities:
        return False

    def toggle_service(service):
        """Handle a calls to the input boolean services."""
        target_inputs = component.extract_from_service(service)

        for input_b in target_inputs:
            if service.service == SERVICE_TURN_ON:
                input_b.turn_on()
            else:
                input_b.turn_off()

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, toggle_service,
                           schema=TOGGLE_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_TURN_ON, toggle_service,
                           schema=TOGGLE_SERVICE_SCHEMA)

    component.add_entities(entities)

    return True


class InputBoolean(ToggleEntity):
    """Representation of a boolean input."""

    def __init__(self, object_id, name, state, icon):
        """Initialize a boolean input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._state = state
        self._icon = icon

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the boolean input."""
        return self._name

    @property
    def icon(self):
        """Returh the icon to be used for this entity."""
        return self._icon

    @property
    def is_on(self):
        """Return true if entity is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False
        self.update_ha_state()
