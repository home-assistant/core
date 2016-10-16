"""
Support for scripts.

Scripts are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/script/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, STATE_ON, CONF_ALIAS)
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.script import Script

DOMAIN = "script"
ENTITY_ID_FORMAT = DOMAIN + '.{}'
GROUP_NAME_ALL_SCRIPTS = 'all scripts'
DEPENDENCIES = ["group"]

CONF_SEQUENCE = "sequence"

ATTR_VARIABLES = 'variables'
ATTR_LAST_ACTION = 'last_action'
ATTR_CAN_CANCEL = 'can_cancel'

_LOGGER = logging.getLogger(__name__)

_SCRIPT_ENTRY_SCHEMA = vol.Schema({
    CONF_ALIAS: cv.string,
    vol.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
})

CONFIG_SCHEMA = vol.Schema({
    vol.Required(DOMAIN): {cv.slug: _SCRIPT_ENTRY_SCHEMA}
}, extra=vol.ALLOW_EXTRA)

SCRIPT_SERVICE_SCHEMA = vol.Schema(dict)
SCRIPT_TURN_ONOFF_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_VARIABLES): dict,
})


def is_on(hass, entity_id):
    """Return if the switch is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id, variables=None):
    """Turn script on."""
    _, object_id = split_entity_id(entity_id)

    hass.services.call(DOMAIN, object_id, variables)


def turn_off(hass, entity_id):
    """Turn script on."""
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})


def toggle(hass, entity_id):
    """Toggle the script."""
    hass.services.call(DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id})


def setup(hass, config):
    """Load the scripts from the configuration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                group_name=GROUP_NAME_ALL_SCRIPTS)

    def service_handler(service):
        """Execute a service call to script.<script name>."""
        entity_id = ENTITY_ID_FORMAT.format(service.service)
        script = component.entities.get(entity_id)
        if script.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        script.turn_on(variables=service.data)

    for object_id, cfg in config[DOMAIN].items():
        alias = cfg.get(CONF_ALIAS, object_id)
        script = ScriptEntity(hass, object_id, alias, cfg[CONF_SEQUENCE])
        component.add_entities((script,))
        hass.services.register(DOMAIN, object_id, service_handler,
                               schema=SCRIPT_SERVICE_SCHEMA)

    def turn_on_service(service):
        """Call a service to turn script on."""
        # We could turn on script directly here, but we only want to offer
        # one way to do it. Otherwise no easy way to detect invocations.
        for script in component.extract_from_service(service):
            turn_on(hass, script.entity_id, service.data.get(ATTR_VARIABLES))

    def turn_off_service(service):
        """Cancel a script."""
        for script in component.extract_from_service(service):
            script.turn_off()

    def toggle_service(service):
        """Toggle a script."""
        for script in component.extract_from_service(service):
            script.toggle()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, turn_on_service,
                           schema=SCRIPT_TURN_ONOFF_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, turn_off_service,
                           schema=SCRIPT_TURN_ONOFF_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_TOGGLE, toggle_service,
                           schema=SCRIPT_TURN_ONOFF_SCHEMA)
    return True


class ScriptEntity(ToggleEntity):
    """Representation of a script entity."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, object_id, name, sequence):
        """Initialize the script."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self.script = Script(hass, sequence, name, self.async_update_ha_state)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self.script.name

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self.script.can_cancel:
            attrs[ATTR_CAN_CANCEL] = self.script.can_cancel
        if self.script.last_action:
            attrs[ATTR_LAST_ACTION] = self.script.last_action
        return attrs

    @property
    def is_on(self):
        """Return true if script is on."""
        return self.script.is_running

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        self.script.run(kwargs.get(ATTR_VARIABLES))

    def turn_off(self, **kwargs):
        """Turn script off."""
        self.script.stop()
