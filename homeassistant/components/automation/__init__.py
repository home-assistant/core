"""Allow to set up simple automation rules via the config file."""
import asyncio
import importlib
import logging
from typing import Any, Awaitable, Callable, List, Optional, Set

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_PLATFORM,
    CONF_ZONE,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Context, CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, extract_domain_configs, script
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.loader import bind_hass
from homeassistant.util.dt import parse_datetime, utcnow

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any

DOMAIN = "automation"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

GROUP_NAME_ALL_AUTOMATIONS = "all automations"

CONF_ALIAS = "alias"
CONF_DESCRIPTION = "description"
CONF_HIDE_ENTITY = "hide_entity"

CONF_CONDITION = "condition"
CONF_ACTION = "action"
CONF_TRIGGER = "trigger"
CONF_CONDITION_TYPE = "condition_type"
CONF_INITIAL_STATE = "initial_state"
CONF_SKIP_CONDITION = "skip_condition"

CONDITION_USE_TRIGGER_VALUES = "use_trigger_values"
CONDITION_TYPE_AND = "and"
CONDITION_TYPE_NOT = "not"
CONDITION_TYPE_OR = "or"

DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND
DEFAULT_INITIAL_STATE = True

EVENT_AUTOMATION_RELOADED = "automation_reloaded"
EVENT_AUTOMATION_TRIGGERED = "automation_triggered"

ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_VARIABLES = "variables"
SERVICE_TRIGGER = "trigger"

_LOGGER = logging.getLogger(__name__)

AutomationActionType = Callable[[HomeAssistant, TemplateVarsType], Awaitable[None]]


def _platform_validator(config):
    """Validate it is a valid platform."""
    try:
        platform = importlib.import_module(f".{config[CONF_PLATFORM]}", __name__)
    except ImportError:
        raise vol.Invalid("Invalid platform specified") from None

    return platform.TRIGGER_SCHEMA(config)


_TRIGGER_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.All(
            vol.Schema({vol.Required(CONF_PLATFORM): str}, extra=vol.ALLOW_EXTRA),
            _platform_validator,
        )
    ],
)

_CONDITION_SCHEMA = vol.All(cv.ensure_list, [cv.CONDITION_SCHEMA])

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HIDE_ENTITY, invalidation_version="0.110"),
    vol.Schema(
        {
            # str on purpose
            CONF_ID: str,
            CONF_ALIAS: cv.string,
            vol.Optional(CONF_DESCRIPTION): cv.string,
            vol.Optional(CONF_INITIAL_STATE): cv.boolean,
            vol.Optional(CONF_HIDE_ENTITY): cv.boolean,
            vol.Required(CONF_TRIGGER): _TRIGGER_SCHEMA,
            vol.Optional(CONF_CONDITION): _CONDITION_SCHEMA,
            vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
        }
    ),
)


@bind_hass
def is_on(hass, entity_id):
    """
    Return true if specified automation entity_id is on.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


@callback
def automations_with_entity(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all automations that reference the entity."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    return [
        automation_entity.entity_id
        for automation_entity in component.entities
        if entity_id in automation_entity.referenced_entities
    ]


@callback
def entities_in_automation(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all entities in a scene."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    automation_entity = component.get_entity(entity_id)

    if automation_entity is None:
        return []

    return list(automation_entity.referenced_entities)


@callback
def automations_with_device(hass: HomeAssistant, device_id: str) -> List[str]:
    """Return all automations that reference the device."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    return [
        automation_entity.entity_id
        for automation_entity in component.entities
        if device_id in automation_entity.referenced_devices
    ]


@callback
def devices_in_automation(hass: HomeAssistant, entity_id: str) -> List[str]:
    """Return all devices in a scene."""
    if DOMAIN not in hass.data:
        return []

    component = hass.data[DOMAIN]

    automation_entity = component.get_entity(entity_id)

    if automation_entity is None:
        return []

    return list(automation_entity.referenced_devices)


async def async_setup(hass, config):
    """Set up the automation."""
    hass.data[DOMAIN] = component = EntityComponent(_LOGGER, DOMAIN, hass)

    await _async_process_config(hass, config, component)

    async def trigger_service_handler(entity, service_call):
        """Handle automation triggers."""
        await entity.async_trigger(
            service_call.data[ATTR_VARIABLES],
            skip_condition=service_call.data[CONF_SKIP_CONDITION],
            context=service_call.context,
        )

    component.async_register_entity_service(
        SERVICE_TRIGGER,
        {
            vol.Optional(ATTR_VARIABLES, default={}): dict,
            vol.Optional(CONF_SKIP_CONDITION, default=True): bool,
        },
        trigger_service_handler,
    )
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")

    async def reload_service_handler(service_call):
        """Remove all automations and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await _async_process_config(hass, conf, component)
        hass.bus.async_fire(EVENT_AUTOMATION_RELOADED, context=service_call.context)

    async_register_admin_service(
        hass, DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        return {
            "name": event.data.get(ATTR_NAME),
            "message": "has been triggered",
            "entity_id": event.data.get(ATTR_ENTITY_ID),
        }

    hass.components.logbook.async_describe_event(
        DOMAIN, EVENT_AUTOMATION_TRIGGERED, async_describe_logbook_event
    )

    return True


class AutomationEntity(ToggleEntity, RestoreEntity):
    """Entity to show status of entity."""

    def __init__(
        self,
        automation_id,
        name,
        trigger_config,
        cond_func,
        action_script,
        initial_state,
    ):
        """Initialize an automation entity."""
        self._id = automation_id
        self._name = name
        self._trigger_config = trigger_config
        self._async_detach_triggers = None
        self._cond_func = cond_func
        self.action_script = action_script
        self._last_triggered = None
        self._initial_state = initial_state
        self._is_enabled = False
        self._referenced_entities: Optional[Set[str]] = None
        self._referenced_devices: Optional[Set[str]] = None

    @property
    def name(self):
        """Name of the automation."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._id

    @property
    def should_poll(self):
        """No polling needed for automation entities."""
        return False

    @property
    def state_attributes(self):
        """Return the entity state attributes."""
        return {ATTR_LAST_TRIGGERED: self._last_triggered}

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._async_detach_triggers is not None or self._is_enabled

    @property
    def referenced_devices(self):
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        referenced = self.action_script.referenced_devices

        if self._cond_func is not None:
            for conf in self._cond_func.config:
                referenced |= condition.async_extract_devices(conf)

        for conf in self._trigger_config:
            device = _trigger_extract_device(conf)
            if device is not None:
                referenced.add(device)

        self._referenced_devices = referenced
        return referenced

    @property
    def referenced_entities(self):
        """Return a set of referenced entities."""
        if self._referenced_entities is not None:
            return self._referenced_entities

        referenced = self.action_script.referenced_entities

        if self._cond_func is not None:
            for conf in self._cond_func.config:
                referenced |= condition.async_extract_entities(conf)

        for conf in self._trigger_config:
            for entity_id in _trigger_extract_entities(conf):
                referenced.add(entity_id)

        self._referenced_entities = referenced
        return referenced

    async def async_added_to_hass(self) -> None:
        """Startup with initial state or previous state."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            enable_automation = state.state == STATE_ON
            last_triggered = state.attributes.get("last_triggered")
            if last_triggered is not None:
                self._last_triggered = parse_datetime(last_triggered)
            _LOGGER.debug(
                "Loaded automation %s with state %s from state "
                " storage last state %s",
                self.entity_id,
                enable_automation,
                state,
            )
        else:
            enable_automation = DEFAULT_INITIAL_STATE
            _LOGGER.debug(
                "Automation %s not in state storage, state %s from default is used.",
                self.entity_id,
                enable_automation,
            )

        if self._initial_state is not None:
            enable_automation = self._initial_state
            _LOGGER.debug(
                "Automation %s initial state %s overridden from "
                "config initial_state",
                self.entity_id,
                enable_automation,
            )

        if enable_automation:
            await self.async_enable()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on and update the state."""
        await self.async_enable()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_disable()

    async def async_trigger(self, variables, skip_condition=False, context=None):
        """Trigger automation.

        This method is a coroutine.
        """
        if (
            not skip_condition
            and self._cond_func is not None
            and not self._cond_func(variables)
        ):
            return

        # Create a new context referring to the old context.
        parent_id = None if context is None else context.id
        trigger_context = Context(parent_id=parent_id)

        self.async_set_context(trigger_context)
        self._last_triggered = utcnow()
        self.async_write_ha_state()
        self.hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {ATTR_NAME: self._name, ATTR_ENTITY_ID: self.entity_id},
            context=trigger_context,
        )

        _LOGGER.info("Executing %s", self._name)

        try:
            await self.action_script.async_run(variables, trigger_context)
        except Exception:  # pylint: disable=broad-except
            pass

    async def async_will_remove_from_hass(self):
        """Remove listeners when removing automation from Home Assistant."""
        await super().async_will_remove_from_hass()
        await self.async_disable()

    async def async_enable(self):
        """Enable this automation entity.

        This method is a coroutine.
        """
        if self._is_enabled:
            return

        self._is_enabled = True

        # HomeAssistant is starting up
        if self.hass.state != CoreState.not_running:
            self._async_detach_triggers = await self._async_attach_triggers(False)
            self.async_write_ha_state()
            return

        async def async_enable_automation(event):
            """Start automation on startup."""
            # Don't do anything if no longer enabled or already attached
            if not self._is_enabled or self._async_detach_triggers is not None:
                return

            self._async_detach_triggers = await self._async_attach_triggers(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, async_enable_automation
        )
        self.async_write_ha_state()

    async def async_disable(self):
        """Disable the automation entity."""
        if not self._is_enabled:
            return

        self._is_enabled = False

        if self._async_detach_triggers is not None:
            self._async_detach_triggers()
            self._async_detach_triggers = None

        self.async_write_ha_state()

    async def _async_attach_triggers(
        self, home_assistant_start: bool
    ) -> Optional[Callable[[], None]]:
        """Set up the triggers."""
        info = {"name": self._name, "home_assistant_start": home_assistant_start}

        triggers = []
        for conf in self._trigger_config:
            platform = importlib.import_module(f".{conf[CONF_PLATFORM]}", __name__)

            triggers.append(
                platform.async_attach_trigger(  # type: ignore
                    self.hass, conf, self.async_trigger, info
                )
            )

        results = await asyncio.gather(*triggers)

        if None in results:
            _LOGGER.error("Error setting up trigger %s", self._name)

        removes = [remove for remove in results if remove is not None]
        if not removes:
            return None

        _LOGGER.info("Initialized trigger %s", self._name)

        @callback
        def remove_triggers():
            """Remove attached triggers."""
            for remove in removes:
                remove()

        return remove_triggers

    @property
    def device_state_attributes(self):
        """Return automation attributes."""
        if self._id is None:
            return None

        return {CONF_ID: self._id}


async def _async_process_config(hass, config, component):
    """Process config and add automations.

    This method is a coroutine.
    """
    entities = []

    for config_key in extract_domain_configs(config, DOMAIN):
        conf = config[config_key]

        for list_no, config_block in enumerate(conf):
            automation_id = config_block.get(CONF_ID)
            name = config_block.get(CONF_ALIAS) or f"{config_key} {list_no}"

            initial_state = config_block.get(CONF_INITIAL_STATE)

            action_script = script.Script(
                hass, config_block.get(CONF_ACTION, {}), name, logger=_LOGGER
            )

            if CONF_CONDITION in config_block:
                cond_func = await _async_process_if(hass, config, config_block)

                if cond_func is None:
                    continue
            else:
                cond_func = None

            entity = AutomationEntity(
                automation_id,
                name,
                config_block[CONF_TRIGGER],
                cond_func,
                action_script,
                initial_state,
            )

            entities.append(entity)

    if entities:
        await component.async_add_entities(entities)


async def _async_process_if(hass, config, p_config):
    """Process if checks."""
    if_configs = p_config[CONF_CONDITION]

    checks = []
    for if_config in if_configs:
        try:
            checks.append(await condition.async_from_config(hass, if_config, False))
        except HomeAssistantError as ex:
            _LOGGER.warning("Invalid condition: %s", ex)
            return None

    def if_action(variables=None):
        """AND all conditions."""
        return all(check(hass, variables) for check in checks)

    if_action.config = if_configs

    return if_action


@callback
def _trigger_extract_device(trigger_conf: dict) -> Optional[str]:
    """Extract devices from a trigger config."""
    if trigger_conf[CONF_PLATFORM] != "device":
        return None

    return trigger_conf[CONF_DEVICE_ID]


@callback
def _trigger_extract_entities(trigger_conf: dict) -> List[str]:
    """Extract entities from a trigger config."""
    if trigger_conf[CONF_PLATFORM] in ("state", "numeric_state"):
        return trigger_conf[CONF_ENTITY_ID]

    if trigger_conf[CONF_PLATFORM] == "zone":
        return trigger_conf[CONF_ENTITY_ID] + [trigger_conf[CONF_ZONE]]

    if trigger_conf[CONF_PLATFORM] == "geo_location":
        return [trigger_conf[CONF_ZONE]]

    if trigger_conf[CONF_PLATFORM] == "sun":
        return ["sun.sun"]

    return []
