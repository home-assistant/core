"""Support for scripts."""
import asyncio
import logging
from typing import List

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_ALIAS,
    CONF_ICON,
    EVENT_SCRIPT_STARTED,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.script import Script
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "script"
ATTR_CAN_CANCEL = "can_cancel"
ATTR_LAST_ACTION = "last_action"
ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_VARIABLES = "variables"

CONF_DESCRIPTION = "description"
CONF_EXAMPLE = "example"
CONF_FIELDS = "fields"
CONF_SEQUENCE = "sequence"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCRIPT_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DESCRIPTION, default=""): cv.string,
        vol.Optional(CONF_FIELDS, default={}): {
            cv.string: {
                vol.Optional(CONF_DESCRIPTION): cv.string,
                vol.Optional(CONF_EXAMPLE): cv.string,
            }
        },
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(SCRIPT_ENTRY_SCHEMA)}, extra=vol.ALLOW_EXTRA
)

SCRIPT_SERVICE_SCHEMA = vol.Schema(dict)
SCRIPT_TURN_ONOFF_SCHEMA = make_entity_service_schema(
    {vol.Optional(ATTR_VARIABLES): dict}
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


@bind_hass
def is_on(hass, entity_id):
    """Return if the script is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


@callback
def scripts_with_entity(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all scripts that reference the entity."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    results = []

    for script_entity in component.entities:
        if entity_id in script_entity.script.referenced_entities:
            results.append(script_entity.entity_id)

    return results


@callback
def entities_in_script(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all entities in a scene."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    script_entity = component.get_entity(entity_id)

    if script_entity is None:
        return []

    return list(script_entity.script.referenced_entities)


@callback
def scripts_with_device(hass: HomeAssistant, device_id: str) -> List[str]:
    """Return all scripts that reference the device."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    results = []

    for script_entity in component.entities:
        if device_id in script_entity.script.referenced_devices:
            results.append(script_entity.entity_id)

    return results


@callback
def devices_in_script(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all devices in a scene."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    script_entity = component.get_entity(entity_id)

    if script_entity is None:
        return []

    return list(script_entity.script.referenced_devices)


async def async_setup(hass, config):
    """Load the scripts from the configuration."""
    hass.data[DOMAIN] = component = EntityComponent(_LOGGER, DOMAIN, hass)

    await _async_process_config(hass, config, component)

    async def reload_service(service):
        """Call a service to reload scripts."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return

        await _async_process_config(hass, conf, component)

    async def turn_on_service(service):
        """Call a service to turn script on."""
        # We could turn on script directly here, but we only want to offer
        # one way to do it. Otherwise no easy way to detect invocations.
        var = service.data.get(ATTR_VARIABLES)
        for script in await component.async_extract_from_service(service):
            await hass.services.async_call(
                DOMAIN, script.object_id, var, context=service.context
            )

    async def turn_off_service(service):
        """Cancel a script."""
        # Stopping a script is ok to be done in parallel
        scripts = await component.async_extract_from_service(service)

        if not scripts:
            return

        await asyncio.wait([script.async_turn_off() for script in scripts])

    async def toggle_service(service):
        """Toggle a script."""
        for script in await component.async_extract_from_service(service):
            await script.async_toggle(context=service.context)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service, schema=RELOAD_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, turn_on_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, turn_off_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, toggle_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )

    return True


async def _async_process_config(hass, config, component):
    """Process script configuration."""

    async def service_handler(service):
        """Execute a service call to script.<script name>."""
        entity_id = ENTITY_ID_FORMAT.format(service.service)
        script = component.get_entity(entity_id)
        if script.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        await script.async_turn_on(variables=service.data, context=service.context)

    scripts = []

    for object_id, cfg in config.get(DOMAIN, {}).items():
        scripts.append(
            ScriptEntity(
                hass,
                object_id,
                cfg.get(CONF_ALIAS, object_id),
                cfg.get(CONF_ICON),
                cfg[CONF_SEQUENCE],
            )
        )
        hass.services.async_register(
            DOMAIN, object_id, service_handler, schema=SCRIPT_SERVICE_SCHEMA
        )

        # Register the service description
        service_desc = {
            CONF_DESCRIPTION: cfg[CONF_DESCRIPTION],
            CONF_FIELDS: cfg[CONF_FIELDS],
        }
        async_set_service_schema(hass, DOMAIN, object_id, service_desc)

    await component.async_add_entities(scripts)


class ScriptEntity(ToggleEntity):
    """Representation of a script entity."""

    icon = None

    def __init__(self, hass, object_id, name, icon, sequence):
        """Initialize the script."""
        self.object_id = object_id
        self.icon = icon
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self.script = Script(
            hass, sequence, name, self.async_write_ha_state, logger=_LOGGER
        )

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

    async def async_turn_on(self, **kwargs):
        """Turn the script on."""
        context = kwargs.get("context")
        self.async_set_context(context)
        self.hass.bus.async_fire(
            EVENT_SCRIPT_STARTED,
            {ATTR_NAME: self.script.name, ATTR_ENTITY_ID: self.entity_id},
            context=context,
        )
        await self.script.async_run(kwargs.get(ATTR_VARIABLES), context)

    async def async_turn_off(self, **kwargs):
        """Turn script off."""
        await self.script.async_stop()

    async def async_will_remove_from_hass(self):
        """Stop script and remove service when it will be removed from Home Assistant."""
        await self.script.async_stop()

        # remove service
        self.hass.services.async_remove(DOMAIN, self.object_id)
