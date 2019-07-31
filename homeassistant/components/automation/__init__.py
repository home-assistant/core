"""Allow to set up simple automation rules via the config file."""
import asyncio
from functools import partial
import importlib
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_ID,
    CONF_PLATFORM,
    EVENT_AUTOMATION_TRIGGERED,
    EVENT_HOMEASSISTANT_START,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Context, CoreState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, extract_domain_configs, script
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import ENTITY_SERVICE_SCHEMA
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.loader import bind_hass
from homeassistant.util.dt import parse_datetime, utcnow

DOMAIN = "automation"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

GROUP_NAME_ALL_AUTOMATIONS = "all automations"

CONF_ALIAS = "alias"
CONF_HIDE_ENTITY = "hide_entity"

CONF_CONDITION = "condition"
CONF_ACTION = "action"
CONF_TRIGGER = "trigger"
CONF_CONDITION_TYPE = "condition_type"
CONF_INITIAL_STATE = "initial_state"

CONDITION_USE_TRIGGER_VALUES = "use_trigger_values"
CONDITION_TYPE_AND = "and"
CONDITION_TYPE_OR = "or"

DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND
DEFAULT_HIDE_ENTITY = False
DEFAULT_INITIAL_STATE = True

ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_VARIABLES = "variables"
SERVICE_TRIGGER = "trigger"

_LOGGER = logging.getLogger(__name__)


def _platform_validator(config):
    """Validate it is a valid platform."""
    try:
        platform = importlib.import_module(
            ".{}".format(config[CONF_PLATFORM]), __name__
        )
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

PLATFORM_SCHEMA = vol.Schema(
    {
        # str on purpose
        CONF_ID: str,
        CONF_ALIAS: cv.string,
        vol.Optional(CONF_INITIAL_STATE): cv.boolean,
        vol.Optional(CONF_HIDE_ENTITY, default=DEFAULT_HIDE_ENTITY): cv.boolean,
        vol.Required(CONF_TRIGGER): _TRIGGER_SCHEMA,
        vol.Optional(CONF_CONDITION): _CONDITION_SCHEMA,
        vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
    }
)

TRIGGER_SERVICE_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {vol.Optional(ATTR_VARIABLES, default={}): dict}
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})


@bind_hass
def is_on(hass, entity_id):
    """
    Return true if specified automation entity_id is on.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up the automation."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, group_name=GROUP_NAME_ALL_AUTOMATIONS
    )

    await _async_process_config(hass, config, component)

    async def trigger_service_handler(service_call):
        """Handle automation triggers."""
        tasks = []
        for entity in await component.async_extract_from_service(service_call):
            tasks.append(
                entity.async_trigger(
                    service_call.data.get(ATTR_VARIABLES),
                    skip_condition=True,
                    context=service_call.context,
                )
            )

        if tasks:
            await asyncio.wait(tasks)

    async def turn_onoff_service_handler(service_call):
        """Handle automation turn on/off service calls."""
        tasks = []
        method = "async_{}".format(service_call.service)
        for entity in await component.async_extract_from_service(service_call):
            tasks.append(getattr(entity, method)())

        if tasks:
            await asyncio.wait(tasks)

    async def toggle_service_handler(service_call):
        """Handle automation toggle service calls."""
        tasks = []
        for entity in await component.async_extract_from_service(service_call):
            if entity.is_on:
                tasks.append(entity.async_turn_off())
            else:
                tasks.append(entity.async_turn_on())

        if tasks:
            await asyncio.wait(tasks)

    async def reload_service_handler(service_call):
        """Remove all automations and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await _async_process_config(hass, conf, component)

    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER, trigger_service_handler, schema=TRIGGER_SERVICE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=RELOAD_SERVICE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, toggle_service_handler, schema=ENTITY_SERVICE_SCHEMA
    )

    for service in (SERVICE_TURN_ON, SERVICE_TURN_OFF):
        hass.services.async_register(
            DOMAIN, service, turn_onoff_service_handler, schema=ENTITY_SERVICE_SCHEMA
        )

    return True


class AutomationEntity(ToggleEntity, RestoreEntity):
    """Entity to show status of entity."""

    def __init__(
        self,
        automation_id,
        name,
        async_attach_triggers,
        cond_func,
        async_action,
        hidden,
        initial_state,
    ):
        """Initialize an automation entity."""
        self._id = automation_id
        self._name = name
        self._async_attach_triggers = async_attach_triggers
        self._async_detach_triggers = None
        self._cond_func = cond_func
        self._async_action = async_action
        self._last_triggered = None
        self._hidden = hidden
        self._initial_state = initial_state
        self._is_enabled = False

    @property
    def name(self):
        """Name of the automation."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for automation entities."""
        return False

    @property
    def state_attributes(self):
        """Return the entity state attributes."""
        return {ATTR_LAST_TRIGGERED: self._last_triggered}

    @property
    def hidden(self) -> bool:
        """Return True if the automation entity should be hidden from UIs."""
        return self._hidden

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._async_detach_triggers is not None or self._is_enabled

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
                "Automation %s not in state storage, state %s from " "default is used.",
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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on and update the state."""
        await self.async_enable()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self.async_disable()

    async def async_trigger(self, variables, skip_condition=False, context=None):
        """Trigger automation.

        This method is a coroutine.
        """
        if not skip_condition and not self._cond_func(variables):
            return

        # Create a new context referring to the old context.
        parent_id = None if context is None else context.id
        trigger_context = Context(parent_id=parent_id)

        self.async_set_context(trigger_context)
        self.hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {ATTR_NAME: self._name, ATTR_ENTITY_ID: self.entity_id},
            context=trigger_context,
        )
        await self._async_action(self.entity_id, variables, trigger_context)
        self._last_triggered = utcnow()
        await self.async_update_ha_state()

    async def async_will_remove_from_hass(self):
        """Remove listeners when removing automation from HASS."""
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
            self._async_detach_triggers = await self._async_attach_triggers(
                self.async_trigger
            )
            self.async_write_ha_state()
            return

        async def async_enable_automation(event):
            """Start automation on startup."""
            # Don't do anything if no longer enabled or already attached
            if not self._is_enabled or self._async_detach_triggers is not None:
                return

            self._async_detach_triggers = await self._async_attach_triggers(
                self.async_trigger
            )

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_enable_automation
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
            name = config_block.get(CONF_ALIAS) or "{} {}".format(config_key, list_no)

            hidden = config_block[CONF_HIDE_ENTITY]
            initial_state = config_block.get(CONF_INITIAL_STATE)

            action = _async_get_action(hass, config_block.get(CONF_ACTION, {}), name)

            if CONF_CONDITION in config_block:
                cond_func = _async_process_if(hass, config, config_block)

                if cond_func is None:
                    continue
            else:

                def cond_func(variables):
                    """Condition will always pass."""
                    return True

            async_attach_triggers = partial(
                _async_process_trigger,
                hass,
                config,
                config_block.get(CONF_TRIGGER, []),
                name,
            )
            entity = AutomationEntity(
                automation_id,
                name,
                async_attach_triggers,
                cond_func,
                action,
                hidden,
                initial_state,
            )

            entities.append(entity)

    if entities:
        await component.async_add_entities(entities)


def _async_get_action(hass, config, name):
    """Return an action based on a configuration."""
    script_obj = script.Script(hass, config, name)

    async def action(entity_id, variables, context):
        """Execute an action."""
        _LOGGER.info("Executing %s", name)

        try:
            await script_obj.async_run(variables, context)
        except Exception as err:  # pylint: disable=broad-except
            script_obj.async_log_exception(
                _LOGGER, "Error while executing automation {}".format(entity_id), err
            )

    return action


def _async_process_if(hass, config, p_config):
    """Process if checks."""
    if_configs = p_config.get(CONF_CONDITION)

    checks = []
    for if_config in if_configs:
        try:
            checks.append(condition.async_from_config(if_config, False))
        except HomeAssistantError as ex:
            _LOGGER.warning("Invalid condition: %s", ex)
            return None

    def if_action(variables=None):
        """AND all conditions."""
        return all(check(hass, variables) for check in checks)

    return if_action


async def _async_process_trigger(hass, config, trigger_configs, name, action):
    """Set up the triggers.

    This method is a coroutine.
    """
    removes = []
    info = {"name": name}

    for conf in trigger_configs:
        platform = importlib.import_module(".{}".format(conf[CONF_PLATFORM]), __name__)

        remove = await platform.async_trigger(hass, conf, action, info)

        if not remove:
            _LOGGER.error("Error setting up trigger %s", name)
            continue

        _LOGGER.info("Initialized trigger %s", name)
        removes.append(remove)

    if not removes:
        return None

    def remove_triggers():
        """Remove attached triggers."""
        for remove in removes:
            remove()

    return remove_triggers
