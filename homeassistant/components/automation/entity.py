"""Entities for the automation integration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any, cast, override

import probatio
from propcache.api import cached_property

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ATTR_NAME,
    CONF_PATH,
    STATE_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    CoreState,
    HassJob,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound, TemplateError
from homeassistant.helpers import (
    condition as condition_helper,
    trigger as trigger_helper,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script, ScriptRunResult, script_stack_cv
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.trace import (
    TraceElement,
    script_execution_set,
    trace_append_element,
    trace_get,
    trace_path,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import parse_datetime

from .config import ValidationStatus
from .const import (
    ATTR_SOURCE,
    CONF_STOP_ACTIONS,
    DEFAULT_INITIAL_STATE,
    DEFAULT_STOP_ACTIONS,
    DOMAIN,
    EVENT_AUTOMATION_TRIGGERED,
    LOGGER,
    AutomationEntityCapabilityAttribute,
    AutomationEntityStateAttribute,
)
from .trace import trace_automation


class IfAction(condition_helper.ConditionsChecker):
    """Define the format of if_action."""

    config: list[ConfigType]


class BaseAutomationEntity(ToggleEntity, ABC):
    """Base class for automation entities."""

    _entity_component_unrecorded_attributes = frozenset(
        (
            AutomationEntityStateAttribute.LAST_TRIGGERED,
            AutomationEntityStateAttribute.MODE,
            AutomationEntityStateAttribute.CUR,
            AutomationEntityStateAttribute.MAX,
            AutomationEntityCapabilityAttribute.ID,
        )
    )
    raw_config: ConfigType | None

    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        if self.unique_id is not None:
            return {AutomationEntityCapabilityAttribute.ID: self.unique_id}
        return None

    @cached_property
    @abstractmethod
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""

    @cached_property
    @abstractmethod
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""

    @cached_property
    @abstractmethod
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @cached_property
    @abstractmethod
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""

    @cached_property
    @abstractmethod
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""

    @abstractmethod
    async def async_trigger(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> ScriptRunResult | None:
        """Trigger automation."""


class UnavailableAutomationEntity(BaseAutomationEntity):
    """A non-functional automation entity with its state set to unavailable.

    This class is instantiated when an automation fails to validate.
    """

    _attr_should_poll = False
    _attr_available = False

    def __init__(
        self,
        automation_id: str | None,
        name: str,
        raw_config: ConfigType | None,
        raw_blueprint_inputs: ConfigType | None,
        validation_error: str,
        validation_status: ValidationStatus,
    ) -> None:
        """Initialize an automation entity."""
        self._attr_name = name
        self._attr_unique_id = automation_id
        self.raw_config = raw_config
        self._raw_blueprint_inputs = raw_blueprint_inputs
        self._validation_error = validation_error
        self._validation_status = validation_status

    @cached_property
    @override
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        return set()

    @cached_property
    @override
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""
        return set()

    @cached_property
    @override
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        return set()

    @property
    @override
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        # The config is invalid, but it can still point at its blueprint. Once
        # the blueprint was applied, only its inputs hold that reference.
        for config in (self._raw_blueprint_inputs, self.raw_config):
            if (
                config is not None
                and isinstance(blueprint := config.get(CONF_USE_BLUEPRINT), dict)
                and isinstance(path := blueprint.get(CONF_PATH), str)
            ):
                return path
        return None

    @cached_property
    @override
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        return set()

    @cached_property
    @override
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        return set()

    @override
    async def async_added_to_hass(self) -> None:
        """Create a repair issue to notify the user the automation has errors."""
        await super().async_added_to_hass()
        async_create_issue(
            self.hass,
            DOMAIN,
            f"{self.entity_id}_validation_{self._validation_status}",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key=f"validation_{self._validation_status}",
            translation_placeholders={
                "edit": f"/config/automation/edit/{self.unique_id}",
                "entity_id": self.entity_id,
                "error": self._validation_error,
                "name": self._attr_name or self.entity_id,
            },
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        async_delete_issue(
            self.hass, DOMAIN, f"{self.entity_id}_validation_{self._validation_status}"
        )

    @override
    async def async_trigger(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> None:
        """Trigger automation."""


class AutomationEntity(BaseAutomationEntity, RestoreEntity):
    """Entity to show status of entity."""

    _attr_should_poll = False

    def __init__(
        self,
        automation_id: str | None,
        name: str,
        trigger_config: list[ConfigType],
        condition: IfAction | None,
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
        self._condition = condition
        self.action_script = action_script
        self.action_script.change_listener = self.async_write_ha_state
        self._initial_state = initial_state
        self._is_enabled = False
        self._logger = LOGGER
        self._variables = variables
        self._trigger_variables = trigger_variables
        self.raw_config = raw_config
        self._blueprint_inputs = blueprint_inputs
        self._trace_config = trace_config
        self._attr_unique_id = automation_id

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the entity state attributes."""
        attrs: dict[str, Any] = {
            AutomationEntityStateAttribute.LAST_TRIGGERED: (
                self.action_script.last_triggered
            ),
            AutomationEntityStateAttribute.MODE: self.action_script.script_mode,
            AutomationEntityStateAttribute.CUR: self.action_script.runs,
        }
        if self.action_script.supports_max:
            attrs[AutomationEntityStateAttribute.MAX] = self.action_script.max_runs
        return attrs

    @property
    @override
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._async_detach_triggers is not None or self._is_enabled

    @cached_property
    @override
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        referenced = self.action_script.referenced_labels

        if self._condition is not None:
            for conf in self._condition.config:
                referenced |= condition_helper.async_extract_targets(
                    conf, ATTR_LABEL_ID
                )

        for conf in self._trigger_config:
            referenced |= set(trigger_helper.async_extract_targets(conf, ATTR_LABEL_ID))
        return referenced

    @cached_property
    @override
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""
        referenced = self.action_script.referenced_floors

        if self._condition is not None:
            for conf in self._condition.config:
                referenced |= condition_helper.async_extract_targets(
                    conf, ATTR_FLOOR_ID
                )

        for conf in self._trigger_config:
            referenced |= set(trigger_helper.async_extract_targets(conf, ATTR_FLOOR_ID))
        return referenced

    @cached_property
    @override
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        referenced = self.action_script.referenced_areas

        if self._condition is not None:
            for conf in self._condition.config:
                referenced |= condition_helper.async_extract_targets(conf, ATTR_AREA_ID)

        for conf in self._trigger_config:
            referenced |= set(trigger_helper.async_extract_targets(conf, ATTR_AREA_ID))
        return referenced

    @property
    @override
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    @cached_property
    @override
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        referenced = self.action_script.referenced_devices

        if self._condition is not None:
            for conf in self._condition.config:
                referenced |= condition_helper.async_extract_devices(conf)

        for conf in self._trigger_config:
            referenced |= set(trigger_helper.async_extract_devices(conf))

        return referenced

    @cached_property
    @override
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        referenced = self.action_script.referenced_entities

        if self._condition is not None:
            for conf in self._condition.config:
                referenced |= condition_helper.async_extract_entities(conf)

        for conf in self._trigger_config:
            for entity_id in trigger_helper.async_extract_entities(conf):
                referenced.add(entity_id)

        return referenced

    @override
    async def async_added_to_hass(self) -> None:
        """Startup with initial state or previous state."""
        await super().async_added_to_hass()

        self._logger = logging.getLogger(
            f"{LOGGER.name}.{split_entity_id(self.entity_id)[1]}"
        )
        self.action_script.update_logger(self._logger)

        if state := await self.async_get_last_state():
            enable_automation = state.state == STATE_ON
            last_triggered = state.attributes.get(
                AutomationEntityStateAttribute.LAST_TRIGGERED
            )
            if last_triggered is not None:
                self.action_script.last_triggered = parse_datetime(last_triggered)
            self._logger.debug(
                "Loaded automation %s with state %s from state storage last state %s",
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
                "Automation %s initial state %s overridden from config initial_state",
                self.entity_id,
                enable_automation,
            )

        if enable_automation:
            await self._async_enable()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on and update the state."""
        await self._async_enable()
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if CONF_STOP_ACTIONS in kwargs:
            await self._async_disable(kwargs[CONF_STOP_ACTIONS])
        else:
            await self._async_disable()
        self.async_write_ha_state()

    @override
    async def async_trigger(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> ScriptRunResult | None:
        """Trigger automation.

        This method is a coroutine.
        """
        reason = ""
        alias = ""
        if "trigger" in run_variables:
            if "description" in run_variables["trigger"]:
                reason = f" by {run_variables['trigger']['description']}"
            if "alias" in run_variables["trigger"]:
                alias = f" trigger '{run_variables['trigger']['alias']}'"
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
                    return None

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

            if not skip_condition and self._condition is not None:
                try:
                    conditions_pass = self._condition.async_check(variables=variables)
                except (probatio.Invalid, HomeAssistantError) as err:
                    self._logger.error(
                        "Error while checking conditions of automation %s: %s",
                        self.entity_id,
                        err,
                    )
                    automation_trace.set_error(err)
                    return None
                except Exception as err:
                    self._logger.exception(
                        "Unexpected error while checking conditions of automation %s",
                        self.entity_id,
                    )
                    automation_trace.set_error(err)
                    return None

                if not conditions_pass:
                    self._logger.debug(
                        "Conditions not met, aborting automation. Condition summary: %s",
                        trace_get(clear=False),
                    )
                    script_execution_set("failed_conditions")
                    return None

            self.async_set_context(trigger_context)
            event_data = {
                ATTR_NAME: self.name,
                ATTR_ENTITY_ID: self.entity_id,
            }
            if "trigger" in variables and "description" in variables["trigger"]:
                event_data[ATTR_SOURCE] = variables["trigger"]["description"]

            @callback
            def started_action() -> None:
                # This is always a callback from a coro so there is no
                # risk of this running in a thread which allows us to use
                # async_fire_internal
                self.hass.bus.async_fire_internal(
                    EVENT_AUTOMATION_TRIGGERED, event_data, context=trigger_context
                )

            # Make a new empty script stack; automations are allowed
            # to recursively trigger themselves
            script_stack_cv.set([])

            try:
                with trace_path("action"):
                    return await self.action_script.async_run(
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
                        "name": self._attr_name or self.entity_id,
                        "edit": f"/config/automation/edit/{self.unique_id}",
                    },
                )
                automation_trace.set_error(err)
            except (probatio.Invalid, HomeAssistantError) as err:
                self._logger.error(
                    "Error while executing automation %s: %s",
                    self.entity_id,
                    err,
                )
                automation_trace.set_error(err)
            except Exception as err:
                self._logger.exception(
                    "Unexpected error while executing automation %s", self.entity_id
                )
                automation_trace.set_error(err)

            return None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners when removing automation from Home Assistant."""
        await super().async_will_remove_from_hass()
        if self.registry_entry and self.registry_entry.entity_id != self.entity_id:
            # Entity ID change, do not unload the script or conditions as they will
            # be reused.
            await self._async_disable()
            return
        await self._async_disable(stop_actions=False)
        await self.action_script.async_unload()
        if self._condition is not None:
            self._condition.async_unload()

    async def _async_enable_automation(self) -> None:
        """Arm the automation's triggers on startup."""
        # Don't do anything if no longer enabled or already attached
        if not self._is_enabled or self._async_detach_triggers is not None:
            return

        self._async_detach_triggers = await self._async_attach_triggers()
        self.async_write_ha_state()

    async def _async_enable(self) -> None:
        """Enable this automation entity.

        This method is not expected to write state to the
        state machine.
        """
        if self._is_enabled:
            return

        self._is_enabled = True
        # HomeAssistant is starting up
        if self.hass.state is not CoreState.not_running:
            self._async_detach_triggers = await self._async_attach_triggers()
            return

        # Arm the triggers in a startup job, which runs after all listeners to
        # EVENT_HOMEASSISTANT_START have run but before EVENT_HOMEASSISTANT_STARTED
        # has fired. This ensures automations do not fire during startup, but
        # triggers listening for the started event are armed in time to catch it.
        self.hass.async_add_startup_job(HassJob(self._async_enable_automation))

    async def _async_disable(self, stop_actions: bool = DEFAULT_STOP_ACTIONS) -> None:
        """Disable the automation entity.

        This method is not expected to write state to the
        state machine.
        """
        if not self._is_enabled and not self.action_script.runs:
            return

        self._is_enabled = False

        if self._async_detach_triggers is not None:
            self._async_detach_triggers()
            self._async_detach_triggers = None

        if stop_actions:
            await self.action_script.async_stop()

    def _log_callback(self, level: int, msg: str, **kwargs: Any) -> None:
        """Log helper callback."""
        self._logger.log(level, "%s %s", msg, self.name, **kwargs)

    async def _async_trigger_if_enabled(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> ScriptRunResult | None:
        """Trigger automation if enabled.

        If the trigger starts but has a delay, the automation will be triggered
        when the delay has passed so we need to make sure its still enabled before
        executing the action.
        """
        if not self._is_enabled:
            return None
        return await self.async_trigger(run_variables, context, skip_condition)

    @callback
    def _handle_not_triggered(
        self,
        run_variables: dict[str, Any],
        info: trigger_helper.NotTriggeredInfo,
        context: Context | None = None,
    ) -> None:
        """Record a trace for a trigger that evaluated a change but did not fire.

        This is the diagnostic sibling of async_trigger: a trigger calls it - in
        certain interesting cases - when it does not run the action, so the user
        can see in the trace why the automation was not triggered.
        """
        if not self._is_enabled:
            return

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
            not_triggered=True,
        ) as automation_trace:
            automation_trace.set_trace(trace_get())

            trigger_description = run_variables.get("trigger", {}).get("description")
            automation_trace.set_trigger_description(trigger_description)

            # Record the trigger and its diagnostics as the trigger step.
            if "idx" in run_variables.get("trigger", {}):
                trigger_path = f"trigger/{run_variables['trigger']['idx']}"
            else:
                trigger_path = "trigger"
            trace_element = TraceElement(run_variables, trigger_path)
            trace_element.set_result(**info.as_dict())
            trace_append_element(trace_element)

            script_execution_set("not_triggered")

    async def _async_attach_triggers(self) -> Callable[[], None] | None:
        """Set up the triggers."""
        this = None
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

        return await trigger_helper.async_initialize_triggers(
            self.hass,
            self._trigger_config,
            self._async_trigger_if_enabled,
            DOMAIN,
            str(self.name),
            self._log_callback,
            variables=variables,
            did_not_trigger=self._handle_not_triggered,
        )
