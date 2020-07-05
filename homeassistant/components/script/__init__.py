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
    CONF_MODE,
    CONF_QUEUE_SIZE,
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
from homeassistant.helpers.script import (
    SCRIPT_BASE_SCHEMA,
    SCRIPT_MODE_LEGACY,
    Script,
    validate_queue_size,
    warn_deprecated_legacy,
)
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

EVENT_SCRIPT_STARTED = "script_started"


def _deprecated_legacy_mode(config):
    legacy_scripts = []
    for object_id, cfg in config.items():
        mode = cfg.get(CONF_MODE)
        if mode is None:
            legacy_scripts.append(object_id)
            cfg[CONF_MODE] = SCRIPT_MODE_LEGACY
    if legacy_scripts:
        warn_deprecated_legacy(_LOGGER, f"script(s): {', '.join(legacy_scripts)}")
    return config


SCRIPT_ENTRY_SCHEMA = vol.All(
    SCRIPT_BASE_SCHEMA.extend(
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
    ),
    validate_queue_size,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.schema_with_slug_keys(SCRIPT_ENTRY_SCHEMA), _deprecated_legacy_mode
        )
    },
    extra=vol.ALLOW_EXTRA,
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

    return [
        script_entity.entity_id
        for script_entity in component.entities
        if entity_id in script_entity.script.referenced_entities
    ]


@callback
def entities_in_script(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all entities in script."""
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

    return [
        script_entity.entity_id
        for script_entity in component.entities
        if device_id in script_entity.script.referenced_devices
    ]


@callback
def devices_in_script(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all devices in script."""
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
        variables = service.data.get(ATTR_VARIABLES)
        for script_entity in await component.async_extract_from_service(service):
            if script_entity.script.is_legacy:
                await hass.services.async_call(
                    DOMAIN, script_entity.object_id, variables, context=service.context
                )
            else:
                await script_entity.async_turn_on(
                    variables=variables, context=service.context, wait=False
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
        for script_entity in await component.async_extract_from_service(service):
            await script_entity.async_toggle(context=service.context)

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
        script_entity = component.get_entity(entity_id)
        if script_entity.script.is_legacy and script_entity.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        await script_entity.async_turn_on(
            variables=service.data, context=service.context
        )

    script_entities = []

    for object_id, cfg in config.get(DOMAIN, {}).items():
        script_entities.append(
            ScriptEntity(
                hass,
                object_id,
                cfg.get(CONF_ALIAS, object_id),
                cfg.get(CONF_ICON),
                cfg[CONF_SEQUENCE],
                cfg[CONF_MODE],
                cfg.get(CONF_QUEUE_SIZE, 0),
            )
        )

    await component.async_add_entities(script_entities)

    # Register services for all entities that were created successfully.
    for script_entity in script_entities:
        object_id = script_entity.object_id
        if component.get_entity(script_entity.entity_id) is None:
            _LOGGER.error("Couldn't load script %s", object_id)
            continue

        cfg = config[DOMAIN][object_id]

        hass.services.async_register(
            DOMAIN, object_id, service_handler, schema=SCRIPT_SERVICE_SCHEMA
        )

        # Register the service description
        service_desc = {
            CONF_DESCRIPTION: cfg[CONF_DESCRIPTION],
            CONF_FIELDS: cfg[CONF_FIELDS],
        }
        async_set_service_schema(hass, DOMAIN, object_id, service_desc)


class ScriptEntity(ToggleEntity):
    """Representation of a script entity."""

    icon = None

    def __init__(self, hass, object_id, name, icon, sequence, mode, queue_size):
        """Initialize the script."""
        self.object_id = object_id
        self.icon = icon
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self.script = Script(
            hass,
            sequence,
            name,
            self.async_change_listener,
            mode,
            queue_size,
            logging.getLogger(f"{__name__}.{object_id}"),
        )
        self._changed = asyncio.Event()

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
        attrs = {ATTR_LAST_TRIGGERED: self.script.last_triggered}
        if self.script.can_cancel:
            attrs[ATTR_CAN_CANCEL] = self.script.can_cancel
        if self.script.last_action:
            attrs[ATTR_LAST_ACTION] = self.script.last_action
        return attrs

    @property
    def is_on(self):
        """Return true if script is on."""
        return self.script.is_running

    @callback
    def async_change_listener(self):
        """Update state."""
        self.async_write_ha_state()
        self._changed.set()

    async def async_turn_on(self, **kwargs):
        """Turn the script on."""
        variables = kwargs.get("variables")
        context = kwargs.get("context")
        wait = kwargs.get("wait", True)
        self.async_set_context(context)
        self.hass.bus.async_fire(
            EVENT_SCRIPT_STARTED,
            {ATTR_NAME: self.script.name, ATTR_ENTITY_ID: self.entity_id},
            context=context,
        )
        coro = self.script.async_run(variables, context)
        if wait:
            await coro
            return

        # Caller does not want to wait for called script to finish so let script run in
        # separate Task. However, wait for first state change so we can guarantee that
        # it is written to the State Machine before we return. Only do this for
        # non-legacy scripts, since legacy scripts don't necessarily change state
        # immediately.
        self._changed.clear()
        self.hass.async_create_task(coro)
        if not self.script.is_legacy:
            await self._changed.wait()

    async def async_turn_off(self, **kwargs):
        """Turn script off."""
        await self.script.async_stop()

    async def async_will_remove_from_hass(self):
        """Stop script and remove service when it will be removed from Home Assistant."""
        await self.script.async_stop()

        # remove service
        self.hass.services.async_remove(DOMAIN, self.object_id)
