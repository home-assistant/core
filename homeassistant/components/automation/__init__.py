"""Allow to set up simple automation rules via the config file."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any, Protocol, cast

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import blueprint, websocket_api
from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_NAME,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_ID,
    CONF_MODE,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_VARIABLES,
    CONF_ZONE,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    CoreState,
    Event,
    HomeAssistant,
    ServiceCall,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    HomeAssistantError,
    ServiceNotFound,
    TemplateError,
)
from homeassistant.helpers import condition, extract_domain_configs
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import (
    ATTR_CUR,
    ATTR_MAX,
    CONF_MAX,
    CONF_MAX_EXCEEDED,
    Script,
    script_stack_cv,
)
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.service import (
    ReloadServiceHelper,
    async_register_admin_service,
)
from homeassistant.helpers.trace import (
    TraceElement,
    script_execution_set,
    trace_append_element,
    trace_get,
    trace_path,
)
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerData,
    TriggerInfo,
    async_initialize_triggers,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.dt import parse_datetime

from .config import AutomationConfig, async_validate_config_item
from .const import (
    CONF_ACTION,
    CONF_INITIAL_STATE,
    CONF_TRACE,
    CONF_TRIGGER,
    CONF_TRIGGER_VARIABLES,
    DEFAULT_INITIAL_STATE,
    DOMAIN,
    LOGGER,
)
from .helpers import async_get_blueprints
from .trace import trace_automation

ENTITY_ID_FORMAT = DOMAIN + ".{}"


CONF_SKIP_CONDITION = "skip_condition"
CONF_STOP_ACTIONS = "stop_actions"
DEFAULT_STOP_ACTIONS = True

EVENT_AUTOMATION_RELOADED = "automation_reloaded"
EVENT_AUTOMATION_TRIGGERED = "automation_triggered"

ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_SOURCE = "source"
ATTR_VARIABLES = "variables"
SERVICE_TRIGGER = "trigger"

_LOGGER = logging.getLogger(__name__)


class IfAction(Protocol):
    """Define the format of if_action."""

    config: list[ConfigType]

    def __call__(self, variables: Mapping[str, Any] | None = None) -> bool:
        """AND all conditions."""


# AutomationActionType, AutomationTriggerData,
# and AutomationTriggerInfo are deprecated as of 2022.9.
AutomationActionType = TriggerActionType
AutomationTriggerData = TriggerData
AutomationTriggerInfo = TriggerInfo


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """
    Return true if specified automation entity_id is on.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


def _automations_with_x(
    hass: HomeAssistant, referenced_id: str, property_name: str
) -> list[str]:
    """Return all automations that reference the x."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[AutomationEntity] = hass.data[DOMAIN]

    return [
        automation_entity.entity_id
        for automation_entity in component.entities
        if referenced_id in getattr(automation_entity, property_name)
    ]


def _x_in_automation(
    hass: HomeAssistant, entity_id: str, property_name: str
) -> list[str]:
    """Return all x in an automation."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[AutomationEntity] = hass.data[DOMAIN]

    if (automation_entity := component.get_entity(entity_id)) is None:
        return []

    return list(getattr(automation_entity, property_name))


@callback
def automations_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all automations that reference the entity."""
    return _automations_with_x(hass, entity_id, "referenced_entities")


@callback
def entities_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all entities in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_entities")


@callback
def automations_with_device(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return all automations that reference the device."""
    return _automations_with_x(hass, device_id, "referenced_devices")


@callback
def devices_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all devices in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_devices")


@callback
def automations_with_area(hass: HomeAssistant, area_id: str) -> list[str]:
    """Return all automations that reference the area."""
    return _automations_with_x(hass, area_id, "referenced_areas")


@callback
def areas_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all areas in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_areas")


@callback
def automations_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all automations that reference the blueprint."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[AutomationEntity] = hass.data[DOMAIN]

    return [
        automation_entity.entity_id
        for automation_entity in component.entities
        if automation_entity.referenced_blueprint == blueprint_path
    ]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up all automations."""
    hass.data[DOMAIN] = component = EntityComponent[AutomationEntity](
        LOGGER, DOMAIN, hass
    )

    # Process integration platforms right away since
    # we will create entities before firing EVENT_COMPONENT_LOADED
    await async_process_integration_platform_for_component(hass, DOMAIN)

    # To register the automation blueprints
    async_get_blueprints(hass)

    if not await _async_process_config(hass, config, component):
        await async_get_blueprints(hass).async_populate()

    async def trigger_service_handler(
        entity: AutomationEntity, service_call: ServiceCall
    ) -> None:
        """Handle forced automation trigger, e.g. from frontend."""
        await entity.async_trigger(
            {**service_call.data[ATTR_VARIABLES], "trigger": {"platform": None}},
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
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        {vol.Optional(CONF_STOP_ACTIONS, default=DEFAULT_STOP_ACTIONS): cv.boolean},
        "async_turn_off",
    )

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Remove all automations and load new ones from config."""
        if (conf := await component.async_prepare_reload()) is None:
            return
        async_get_blueprints(hass).async_reset_cache()
        await _async_process_config(hass, conf, component)
        hass.bus.async_fire(EVENT_AUTOMATION_RELOADED, context=service_call.context)

    reload_helper = ReloadServiceHelper(reload_service_handler)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_helper.execute_service,
        schema=vol.Schema({}),
    )

    websocket_api.async_register_command(hass, websocket_config)

    return True


class AutomationEntity(ToggleEntity, RestoreEntity):
    """Entity to show status of entity."""

    _attr_should_poll = False

    def __init__(
        self,
        automation_id: str | None,
        name: str,
        trigger_config: list[ConfigType],
        cond_func: IfAction | None,
        action_script: Script,
        initial_state: bool | None,
        variables: ScriptVariables | None,
        trigger_variables: ScriptVariables | None,
        raw_config: ConfigType | None,
        blueprint_inputs: ConfigType | None,
        trace_config: ConfigType,
    ) -> None:
        """Initialize an automation entity."""
        self._attr_name = name
        self._trigger_config = trigger_config
        self._async_detach_triggers: CALLBACK_TYPE | None = None
        self._cond_func = cond_func
        self.action_script = action_script
        self.action_script.change_listener = self.async_write_ha_state
        self._initial_state = initial_state
        self._is_enabled = False
        self._referenced_entities: set[str] | None = None
        self._referenced_devices: set[str] | None = None
        self._logger = LOGGER
        self._variables = variables
        self._trigger_variables = trigger_variables
        self.raw_config = raw_config
        self._blueprint_inputs = blueprint_inputs
        self._trace_config = trace_config
        self._attr_unique_id = automation_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the entity state attributes."""
        attrs = {
            ATTR_LAST_TRIGGERED: self.action_script.last_triggered,
            ATTR_MODE: self.action_script.script_mode,
            ATTR_CUR: self.action_script.runs,
        }
        if self.action_script.supports_max:
            attrs[ATTR_MAX] = self.action_script.max_runs
        if self.unique_id is not None:
            attrs[CONF_ID] = self.unique_id
        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._async_detach_triggers is not None or self._is_enabled

    @property
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        return self.action_script.referenced_areas

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    @property
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        referenced = self.action_script.referenced_devices

        if self._cond_func is not None:
            for conf in self._cond_func.config:
                referenced |= condition.async_extract_devices(conf)

        for conf in self._trigger_config:
            referenced |= set(_trigger_extract_devices(conf))

        self._referenced_devices = referenced
        return referenced

    @property
    def referenced_entities(self) -> set[str]:
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

        self._logger = logging.getLogger(
            f"{__name__}.{split_entity_id(self.entity_id)[1]}"
        )
        self.action_script.update_logger(self._logger)

        if state := await self.async_get_last_state():
            enable_automation = state.state == STATE_ON
            last_triggered = state.attributes.get("last_triggered")
            if last_triggered is not None:
                self.action_script.last_triggered = parse_datetime(last_triggered)
            self._logger.debug(
                "Loaded automation %s with state %s from state "
                " storage last state %s",
                self.entity_id,
                enable_automation,
                state,
            )
        else:
            enable_automation = DEFAULT_INITIAL_STATE
            self._logger.debug(
                "Automation %s not in state storage, state %s from default is used",
                self.entity_id,
                enable_automation,
            )

        if self._initial_state is not None:
            enable_automation = self._initial_state
            self._logger.debug(
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
        if CONF_STOP_ACTIONS in kwargs:
            await self.async_disable(kwargs[CONF_STOP_ACTIONS])
        else:
            await self.async_disable()

    async def async_trigger(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> None:
        """Trigger automation.

        This method is a coroutine.
        """
        reason = ""
        alias = ""
        if "trigger" in run_variables:
            if "description" in run_variables["trigger"]:
                reason = f' by {run_variables["trigger"]["description"]}'
            if "alias" in run_variables["trigger"]:
                alias = f' trigger \'{run_variables["trigger"]["alias"]}\''
        self._logger.debug("Automation%s triggered%s", alias, reason)

        # Create a new context referring to the old context.
        parent_id = None if context is None else context.id
        trigger_context = Context(parent_id=parent_id)

        with trace_automation(
            self.hass,
            self.unique_id,
            self.raw_config,
            self._blueprint_inputs,
            trigger_context,
            self._trace_config,
        ) as automation_trace:
            this = None
            if state := self.hass.states.get(self.entity_id):
                this = state.as_dict()
            variables: dict[str, Any] = {"this": this, **(run_variables or {})}
            if self._variables:
                try:
                    variables = self._variables.async_render(self.hass, variables)
                except TemplateError as err:
                    self._logger.error("Error rendering variables: %s", err)
                    automation_trace.set_error(err)
                    return

            # Prepare tracing the automation
            automation_trace.set_trace(trace_get())

            # Set trigger reason
            trigger_description = variables.get("trigger", {}).get("description")
            automation_trace.set_trigger_description(trigger_description)

            # Add initial variables as the trigger step
            if "trigger" in variables and "idx" in variables["trigger"]:
                trigger_path = f"trigger/{variables['trigger']['idx']}"
            else:
                trigger_path = "trigger"
            trace_element = TraceElement(variables, trigger_path)
            trace_append_element(trace_element)

            if (
                not skip_condition
                and self._cond_func is not None
                and not self._cond_func(variables)
            ):
                self._logger.debug(
                    "Conditions not met, aborting automation. Condition summary: %s",
                    trace_get(clear=False),
                )
                script_execution_set("failed_conditions")
                return

            self.async_set_context(trigger_context)
            event_data = {
                ATTR_NAME: self.name,
                ATTR_ENTITY_ID: self.entity_id,
            }
            if "trigger" in variables and "description" in variables["trigger"]:
                event_data[ATTR_SOURCE] = variables["trigger"]["description"]

            @callback
            def started_action() -> None:
                self.hass.bus.async_fire(
                    EVENT_AUTOMATION_TRIGGERED, event_data, context=trigger_context
                )

            # Make a new empty script stack; automations are allowed
            # to recursively trigger themselves
            script_stack_cv.set([])

            try:
                with trace_path("action"):
                    await self.action_script.async_run(
                        variables, trigger_context, started_action
                    )
            except ServiceNotFound as err:
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"{self.entity_id}_service_not_found_{err.domain}.{err.service}",
                    is_fixable=True,
                    is_persistent=True,
                    severity=IssueSeverity.ERROR,
                    translation_key="service_not_found",
                    translation_placeholders={
                        "service": f"{err.domain}.{err.service}",
                        "entity_id": self.entity_id,
                        "name": self.name or self.entity_id,
                        "edit": f"/config/automation/edit/{self.unique_id}",
                    },
                )
                automation_trace.set_error(err)
            except (vol.Invalid, HomeAssistantError) as err:
                self._logger.error(
                    "Error while executing automation %s: %s",
                    self.entity_id,
                    err,
                )
                automation_trace.set_error(err)
            except Exception as err:  # pylint: disable=broad-except
                self._logger.exception("While executing automation %s", self.entity_id)
                automation_trace.set_error(err)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners when removing automation from Home Assistant."""
        await super().async_will_remove_from_hass()
        await self.async_disable()

    async def async_enable(self) -> None:
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

        async def async_enable_automation(event: Event) -> None:
            """Start automation on startup."""
            # Don't do anything if no longer enabled or already attached
            if not self._is_enabled or self._async_detach_triggers is not None:
                return

            self._async_detach_triggers = await self._async_attach_triggers(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, async_enable_automation
        )
        self.async_write_ha_state()

    async def async_disable(self, stop_actions: bool = DEFAULT_STOP_ACTIONS) -> None:
        """Disable the automation entity."""
        if not self._is_enabled and not self.action_script.runs:
            return

        self._is_enabled = False

        if self._async_detach_triggers is not None:
            self._async_detach_triggers()
            self._async_detach_triggers = None

        if stop_actions:
            await self.action_script.async_stop()

        self.async_write_ha_state()

    async def _async_attach_triggers(
        self, home_assistant_start: bool
    ) -> Callable[[], None] | None:
        """Set up the triggers."""

        def log_cb(level: int, msg: str, **kwargs: Any) -> None:
            self._logger.log(level, "%s %s", msg, self.name, **kwargs)

        this = None
        self.async_write_ha_state()
        if state := self.hass.states.get(self.entity_id):
            this = state.as_dict()
        variables = {"this": this}
        if self._trigger_variables:
            try:
                variables = self._trigger_variables.async_render(
                    self.hass,
                    variables,
                    limited=True,
                )
            except TemplateError as err:
                self._logger.error("Error rendering trigger variables: %s", err)
                return None

        return await async_initialize_triggers(
            self.hass,
            self._trigger_config,
            self.async_trigger,
            DOMAIN,
            str(self.name),
            log_cb,
            home_assistant_start,
            variables,
        )


async def _async_process_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    component: EntityComponent[AutomationEntity],
) -> bool:
    """Process config and add automations.

    Returns if blueprints were used.
    """
    entities: list[AutomationEntity] = []
    blueprints_used = False

    for config_key in extract_domain_configs(config, DOMAIN):
        conf: list[dict[str, Any] | blueprint.BlueprintInputs] = config[config_key]

        for list_no, config_block in enumerate(conf):
            raw_blueprint_inputs = None
            raw_config = None
            if isinstance(config_block, blueprint.BlueprintInputs):
                blueprints_used = True
                blueprint_inputs = config_block
                raw_blueprint_inputs = blueprint_inputs.config_with_inputs

                try:
                    raw_config = blueprint_inputs.async_substitute()
                    config_block = cast(
                        dict[str, Any],
                        await async_validate_config_item(hass, raw_config),
                    )
                except vol.Invalid as err:
                    LOGGER.error(
                        "Blueprint %s generated invalid automation with inputs %s: %s",
                        blueprint_inputs.blueprint.name,
                        blueprint_inputs.inputs,
                        humanize_error(config_block, err),
                    )
                    continue
            else:
                raw_config = cast(AutomationConfig, config_block).raw_config

            automation_id: str | None = config_block.get(CONF_ID)
            name: str = config_block.get(CONF_ALIAS) or f"{config_key} {list_no}"

            initial_state: bool | None = config_block.get(CONF_INITIAL_STATE)

            action_script = Script(
                hass,
                config_block[CONF_ACTION],
                name,
                DOMAIN,
                running_description="automation actions",
                script_mode=config_block[CONF_MODE],
                max_runs=config_block[CONF_MAX],
                max_exceeded=config_block[CONF_MAX_EXCEEDED],
                logger=LOGGER,
                # We don't pass variables here
                # Automation will already render them to use them in the condition
                # and so will pass them on to the script.
            )

            if CONF_CONDITION in config_block:
                cond_func = await _async_process_if(hass, name, config, config_block)

                if cond_func is None:
                    continue
            else:
                cond_func = None

            # Add trigger variables to variables
            variables = None
            if CONF_TRIGGER_VARIABLES in config_block:
                variables = ScriptVariables(
                    dict(config_block[CONF_TRIGGER_VARIABLES].as_dict())
                )
            if CONF_VARIABLES in config_block:
                if variables:
                    variables.variables.update(config_block[CONF_VARIABLES].as_dict())
                else:
                    variables = config_block[CONF_VARIABLES]

            entity = AutomationEntity(
                automation_id,
                name,
                config_block[CONF_TRIGGER],
                cond_func,
                action_script,
                initial_state,
                variables,
                config_block.get(CONF_TRIGGER_VARIABLES),
                raw_config,
                raw_blueprint_inputs,
                config_block[CONF_TRACE],
            )

            entities.append(entity)

    if entities:
        await component.async_add_entities(entities)

    return blueprints_used


async def _async_process_if(
    hass: HomeAssistant, name: str, config: dict[str, Any], p_config: dict[str, Any]
) -> IfAction | None:
    """Process if checks."""
    if_configs = p_config[CONF_CONDITION]

    checks: list[condition.ConditionCheckerType] = []
    for if_config in if_configs:
        try:
            checks.append(await condition.async_from_config(hass, if_config))
        except HomeAssistantError as ex:
            LOGGER.warning("Invalid condition: %s", ex)
            return None

    def if_action(variables: Mapping[str, Any] | None = None) -> bool:
        """AND all conditions."""
        errors: list[ConditionErrorIndex] = []
        for index, check in enumerate(checks):
            try:
                with trace_path(["condition", str(index)]):
                    if not check(hass, variables):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "condition", index=index, total=len(checks), error=ex
                    )
                )

        if errors:
            LOGGER.warning(
                "Error evaluating condition in '%s':\n%s",
                name,
                ConditionErrorContainer("condition", errors=errors),
            )
            return False

        return True

    result: IfAction = if_action  # type: ignore[assignment]
    result.config = if_configs

    return result


@callback
def _trigger_extract_devices(trigger_conf: dict) -> list[str]:
    """Extract devices from a trigger config."""
    if trigger_conf[CONF_PLATFORM] == "device":
        return [trigger_conf[CONF_DEVICE_ID]]

    if (
        trigger_conf[CONF_PLATFORM] == "event"
        and CONF_EVENT_DATA in trigger_conf
        and CONF_DEVICE_ID in trigger_conf[CONF_EVENT_DATA]
        and isinstance(trigger_conf[CONF_EVENT_DATA][CONF_DEVICE_ID], str)
    ):
        return [trigger_conf[CONF_EVENT_DATA][CONF_DEVICE_ID]]

    if trigger_conf[CONF_PLATFORM] == "tag" and CONF_DEVICE_ID in trigger_conf:
        return trigger_conf[CONF_DEVICE_ID]  # type: ignore[no-any-return]

    return []


@callback
def _trigger_extract_entities(trigger_conf: dict) -> list[str]:
    """Extract entities from a trigger config."""
    if trigger_conf[CONF_PLATFORM] in ("state", "numeric_state"):
        return trigger_conf[CONF_ENTITY_ID]  # type: ignore[no-any-return]

    if trigger_conf[CONF_PLATFORM] == "calendar":
        return [trigger_conf[CONF_ENTITY_ID]]

    if trigger_conf[CONF_PLATFORM] == "zone":
        return trigger_conf[CONF_ENTITY_ID] + [trigger_conf[CONF_ZONE]]  # type: ignore[no-any-return]

    if trigger_conf[CONF_PLATFORM] == "geo_location":
        return [trigger_conf[CONF_ZONE]]

    if trigger_conf[CONF_PLATFORM] == "sun":
        return ["sun.sun"]

    if (
        trigger_conf[CONF_PLATFORM] == "event"
        and CONF_EVENT_DATA in trigger_conf
        and CONF_ENTITY_ID in trigger_conf[CONF_EVENT_DATA]
        and isinstance(trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID], str)
        and valid_entity_id(trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID])
    ):
        return [trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID]]

    return []


@websocket_api.websocket_command({"type": "automation/config", "entity_id": str})
def websocket_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get automation config."""
    component: EntityComponent[AutomationEntity] = hass.data[DOMAIN]

    automation = component.get_entity(msg["entity_id"])

    if automation is None:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Entity not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "config": automation.raw_config,
        },
    )
