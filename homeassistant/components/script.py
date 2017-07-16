"""
Support for scripts.

Scripts are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/script/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, SERVICE_RELOAD, STATE_ON, CONF_ALIAS)
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'script'
DEPENDENCIES = ['group']

ATTR_CAN_CANCEL = 'can_cancel'
ATTR_LAST_ACTION = 'last_action'
ATTR_LAST_TRIGGERED = 'last_triggered'
ATTR_VARIABLES = 'variables'

CONF_SEQUENCE = 'sequence'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

GROUP_NAME_ALL_SCRIPTS = 'all scripts'

_SCRIPT_ENTRY_SCHEMA = vol.Schema({
    CONF_ALIAS: cv.string,
    vol.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({cv.slug: _SCRIPT_ENTRY_SCHEMA})
}, extra=vol.ALLOW_EXTRA)

SCRIPT_SERVICE_SCHEMA = vol.Schema(dict)
SCRIPT_TURN_ONOFF_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_VARIABLES): dict,
})
RELOAD_SERVICE_SCHEMA = vol.Schema({})


def is_on(hass, entity_id):
    """Return if the script is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def reload(hass):
    """Reload script component."""
    hass.services.call(DOMAIN, SERVICE_RELOAD)


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


@asyncio.coroutine
def async_setup(hass, config):
    """Load the scripts from the configuration."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, group_name=GROUP_NAME_ALL_SCRIPTS)

    yield from _async_process_config(hass, config, component)

    @asyncio.coroutine
    def reload_service(service):
        """Call a service to reload scripts."""
        conf = yield from component.async_prepare_reload()
        if conf is None:
            return

        yield from _async_process_config(hass, conf, component)

    @asyncio.coroutine
    def turn_on_service(service):
        """Call a service to turn script on."""
        # We could turn on script directly here, but we only want to offer
        # one way to do it. Otherwise no easy way to detect invocations.
        var = service.data.get(ATTR_VARIABLES)
        for script in component.async_extract_from_service(service):
            yield from hass.services.async_call(DOMAIN, script.object_id, var)

    @asyncio.coroutine
    def turn_off_service(service):
        """Cancel a script."""
        # Stopping a script is ok to be done in parallel
        yield from asyncio.wait(
            [script.async_turn_off() for script
             in component.async_extract_from_service(service)], loop=hass.loop)

    @asyncio.coroutine
    def toggle_service(service):
        """Toggle a script."""
        for script in component.async_extract_from_service(service):
            yield from script.async_toggle()

    hass.services.async_register(DOMAIN, SERVICE_RELOAD, reload_service,
                                 schema=RELOAD_SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_TURN_ON, turn_on_service,
                                 schema=SCRIPT_TURN_ONOFF_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_TURN_OFF, turn_off_service,
                                 schema=SCRIPT_TURN_ONOFF_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_TOGGLE, toggle_service,
                                 schema=SCRIPT_TURN_ONOFF_SCHEMA)

    return True


@asyncio.coroutine
def _async_process_config(hass, config, component):
    """Process group configuration."""
    @asyncio.coroutine
    def service_handler(service):
        """Execute a service call to script.<script name>."""
        entity_id = ENTITY_ID_FORMAT.format(service.service)
        script = component.entities.get(entity_id)
        if script.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        yield from script.async_turn_on(variables=service.data)

    scripts = []

    for object_id, cfg in config[DOMAIN].items():
        alias = cfg.get(CONF_ALIAS, object_id)
        script = ScriptEntity(hass, object_id, alias, cfg[CONF_SEQUENCE])
        scripts.append(script)
        hass.services.async_register(
            DOMAIN, object_id, service_handler, schema=SCRIPT_SERVICE_SCHEMA)

    yield from component.async_add_entities(scripts)


class ScriptEntity(ToggleEntity):
    """Representation of a script entity."""

    def __init__(self, hass, object_id, name, sequence):
        """Initialize the script."""
        self.object_id = object_id
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
        attrs[ATTR_LAST_TRIGGERED] = self.script.last_triggered
        if self.script.can_cancel:
            attrs[ATTR_CAN_CANCEL] = self.script.can_cancel
        if self.script.last_action:
            attrs[ATTR_LAST_ACTION] = self.script.last_action
        return attrs

    @property
    def is_on(self):
        """Return true if script is on."""
        return self.script.is_running

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the script on."""
        yield from self.script.async_run(kwargs.get(ATTR_VARIABLES))

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn script off."""
        self.script.async_stop()

    def async_remove(self):
        """Remove script from HASS.

        This method must be run in the event loop and returns a coroutine.
        """
        if self.script.is_running:
            self.script.async_stop()

        # remove service
        self.hass.services.async_remove(DOMAIN, self.object_id)

        return super().async_remove()
