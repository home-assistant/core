"""Dry run an automation against the current state, without running actions."""

from collections.abc import Callable, Iterable
from contextvars import copy_context
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from typing import Any

import jinja2
from jinja2 import meta
import probatio

from homeassistant.const import (
    CONF_ABOVE,
    CONF_ALIAS,
    CONF_AT,
    CONF_ATTRIBUTE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    CONF_WEEKDAY,
    WEEKDAYS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import condition as condition_helper
from homeassistant.helpers.script import SCRIPT_MODE_SINGLE
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import Template
from homeassistant.helpers.trace import suppress_template_error_logging, trace_get
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util import dt as dt_util

COMPOUND_CONDITIONS = ("and", "or", "not")
TRIGGER_VARIABLE = "trigger"

# Only used to find the variables a template reads, never to render it
_PARSE_ENV = jinja2.Environment(extensions=["jinja2.ext.loopcontrols", "jinja2.ext.do"])


class ConditionResult(StrEnum):
    """Result of a condition in a dry run."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    DEPENDS_ON_TRIGGER = "depends_on_trigger"
    DISABLED = "disabled"


class TriggerStatus(StrEnum):
    """What can be said about a trigger in a dry run."""

    DISABLED = "disabled"
    ERROR = "error"
    IN_RANGE = "in_range"
    IN_TARGET_STATE = "in_target_state"
    NOT_IN_RANGE = "not_in_range"
    NOT_IN_TARGET_STATE = "not_in_target_state"
    SCHEDULED = "scheduled"
    WAITS_FOR_EVENT = "waits_for_event"


class DryRunReason(StrEnum):
    """Why an automation would not run, or why that is unknown."""

    ALREADY_RUNNING = "already_running"
    AUTOMATION_OFF = "automation_off"
    CONDITION_ERROR = "condition_error"
    CONDITIONS_NOT_MET = "conditions_not_met"
    DEPENDS_ON_TRIGGER = "depends_on_trigger"
    MAX_RUNS_REACHED = "max_runs_reached"


@dataclass(slots=True, kw_only=True)
class DryRunInput:
    """Everything a dry run needs from an automation."""

    enabled: bool
    mode: str
    current_runs: int
    max_runs: int | None
    trigger_config: list[ConfigType]
    condition_config: list[ConfigType]
    this: dict[str, Any] | None
    trigger_variables: ScriptVariables | None
    variables: ScriptVariables | None


def _template_variables(value: Any) -> set[str]:
    """Return the variable names the templates in a config read."""
    if isinstance(value, Template):
        if value.is_static:
            return set()
        try:
            return meta.find_undeclared_variables(_PARSE_ENV.parse(value.template))
        except jinja2.TemplateSyntaxError:
            # Rendering reports the syntax error
            return set()
    if isinstance(value, dict):
        return set().union(*(_template_variables(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_template_variables(item) for item in value))
    return set()


def _trigger_dependent_names(variables: ScriptVariables | None) -> set[str]:
    """Return trigger and the automation variables derived from it."""
    names = {TRIGGER_VARIABLE}
    if variables is None:
        return names
    # Variables can read earlier variables, so follow the definition order
    for name, value in variables.variables.items():
        if _template_variables(value) & names:
            names.add(name)
    return names


def _render_variables(
    hass: HomeAssistant, data: DryRunInput, trigger_names: set[str]
) -> tuple[dict[str, Any], str | None]:
    """Render the variables an automation run would see, without trigger."""
    variables: dict[str, Any] = {"this": data.this}
    try:
        if data.trigger_variables:
            variables = data.trigger_variables.async_render(
                hass, variables, limited=True
            )
        if data.variables:
            independent = ScriptVariables(
                {
                    name: value
                    for name, value in data.variables.variables.items()
                    if name not in trigger_names
                }
            )
            variables = independent.async_render(hass, variables)
    except TemplateError as err:
        return variables, str(err)
    return variables, None


def _is_enabled(config: ConfigType, variables: TemplateVarsType) -> bool:
    """Return if a trigger or condition is enabled, raise on a template error."""
    enabled = config.get(CONF_ENABLED, True)
    if isinstance(enabled, Template):
        enabled = enabled.async_render(variables, limited=True)
    return bool(enabled)


def _combine(condition: str, results: Iterable[ConditionResult]) -> ConditionResult:
    """Combine the results of the children of a compound condition."""
    active = {result for result in results if result is not ConditionResult.DISABLED}
    if condition == "and":
        order = (
            (ConditionResult.FAIL, ConditionResult.FAIL),
            (ConditionResult.ERROR, ConditionResult.ERROR),
            (ConditionResult.DEPENDS_ON_TRIGGER, ConditionResult.DEPENDS_ON_TRIGGER),
        )
        default = ConditionResult.PASS
    elif condition == "or":
        order = (
            (ConditionResult.PASS, ConditionResult.PASS),
            (ConditionResult.DEPENDS_ON_TRIGGER, ConditionResult.DEPENDS_ON_TRIGGER),
            (ConditionResult.ERROR, ConditionResult.ERROR),
        )
        default = ConditionResult.FAIL
    else:
        order = (
            (ConditionResult.PASS, ConditionResult.FAIL),
            (ConditionResult.DEPENDS_ON_TRIGGER, ConditionResult.DEPENDS_ON_TRIGGER),
            (ConditionResult.ERROR, ConditionResult.ERROR),
        )
        default = ConditionResult.PASS
    return next((result for child, result in order if child in active), default)


def _check_leaf(
    checker: condition_helper.ConditionChecker, variables: TemplateVarsType
) -> dict[str, Any]:
    """Check a condition and collect its trace; run in a copied context."""
    condition_trace = trace_get()
    node: dict[str, Any] = {}
    with suppress_template_error_logging():
        try:
            result = checker.async_check(variables=variables)
        except HomeAssistantError as err:
            node["result"] = ConditionResult.ERROR
            node["error"] = str(err)
        else:
            node["result"] = (
                ConditionResult.DISABLED
                if result is None
                else ConditionResult.PASS
                if result
                else ConditionResult.FAIL
            )
    details: dict[str, Any] = {}
    template_errors: list[str] = []
    for path, elements in condition_trace.items():
        for element in elements:
            template_errors.extend(element.template_errors)
            trace = element.as_dict()
            if (result_details := trace.get("result")) is None:
                continue
            if path:
                details.setdefault("sub_results", {})[path] = result_details
            else:
                details.update(
                    {
                        key: value
                        for key, value in result_details.items()
                        if key != "result"
                    }
                )
    if details:
        node["details"] = details
    if template_errors:
        node["template_errors"] = template_errors
    return node


async def _async_evaluate_leaf(
    hass: HomeAssistant, config: ConfigType, variables: TemplateVarsType
) -> dict[str, Any]:
    """Evaluate a condition that is not a compound condition."""
    try:
        checker = await condition_helper.async_from_config(hass, config)
    except HomeAssistantError as err:
        return {"result": ConditionResult.ERROR, "error": str(err)}
    try:
        return copy_context().run(_check_leaf, checker, variables)
    finally:
        checker.async_unload()


async def _async_evaluate_condition(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    path: str,
    trigger_names: set[str],
) -> dict[str, Any]:
    """Evaluate a condition and all of its children."""
    condition: str = config[CONF_CONDITION]
    node: dict[str, Any] = {"path": path, "condition": condition}
    if CONF_ALIAS in config:
        node["alias"] = config[CONF_ALIAS]
    try:
        # Conditions render enabled without the automation variables
        enabled = _is_enabled(config, None)
    except TemplateError as err:
        node.update(result=ConditionResult.ERROR, error=str(err))
        return node
    if not enabled:
        node["result"] = ConditionResult.DISABLED
        return node
    if condition in COMPOUND_CONDITIONS:
        children = [
            await _async_evaluate_condition(
                hass, child, variables, f"{path}/conditions/{index}", trigger_names
            )
            for index, child in enumerate(config["conditions"])
        ]
        node["result"] = _combine(condition, (child["result"] for child in children))
        node["conditions"] = children
        return node
    if condition == "trigger" or _template_variables(config) & trigger_names:
        node["result"] = ConditionResult.DEPENDS_ON_TRIGGER
        return node
    node.update(await _async_evaluate_leaf(hass, config, variables))
    return node


def _next_time(at: time, weekdays: list[str] | None, now: datetime) -> datetime:
    """Return the next local datetime a fixed time trigger fires."""
    candidate = datetime.combine(now.date(), at, tzinfo=now.tzinfo)
    if candidate <= now:
        candidate += timedelta(days=1)
    while weekdays and WEEKDAYS[candidate.weekday()] not in weekdays:
        candidate += timedelta(days=1)
    return candidate


def _state_trigger_condition(config: ConfigType) -> ConfigType | None:
    """Return the condition matching the target of a state trigger."""
    if config.get("to") is None:
        return None
    condition = {
        CONF_CONDITION: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        CONF_STATE: config["to"],
    }
    for key in (CONF_ATTRIBUTE, "for"):
        if key in config:
            condition[key] = config[key]
    return condition


def _numeric_state_trigger_condition(config: ConfigType) -> ConfigType:
    """Return the condition matching the range of a numeric_state trigger."""
    condition = {
        CONF_CONDITION: "numeric_state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }
    for key in (CONF_ABOVE, CONF_BELOW, CONF_ATTRIBUTE, CONF_VALUE_TEMPLATE):
        if key in config:
            condition[key] = config[key]
    return condition


@dataclass(slots=True, frozen=True)
class _TriggerAsCondition:
    """How to check the current state against a trigger's target."""

    to_condition: Callable[[ConfigType], ConfigType | None]
    passed: TriggerStatus
    failed: TriggerStatus


_TRIGGER_AS_CONDITION = {
    "state": _TriggerAsCondition(
        _state_trigger_condition,
        TriggerStatus.IN_TARGET_STATE,
        TriggerStatus.NOT_IN_TARGET_STATE,
    ),
    "numeric_state": _TriggerAsCondition(
        _numeric_state_trigger_condition,
        TriggerStatus.IN_RANGE,
        TriggerStatus.NOT_IN_RANGE,
    ),
}


async def _async_evaluate_trigger(
    hass: HomeAssistant, index: int, config: ConfigType, variables: TemplateVarsType
) -> dict[str, Any]:
    """Describe what the current state means for a trigger."""
    platform: str = config[CONF_PLATFORM]
    node: dict[str, Any] = {
        "idx": str(index),
        "id": config.get(CONF_ID, str(index)),
        "trigger": platform,
    }
    if CONF_ALIAS in config:
        node["alias"] = config[CONF_ALIAS]
    try:
        enabled = _is_enabled(config, variables)
    except TemplateError as err:
        node.update(status=TriggerStatus.ERROR, error=str(err))
        return node
    if not enabled:
        node["status"] = TriggerStatus.DISABLED
        return node

    if platform == "time":
        now = dt_util.now()
        weekdays = config.get(CONF_WEEKDAY)
        if isinstance(weekdays, str):
            weekdays = [weekdays]
        # The time of a helper or sensor is not known without reading its state
        if all(isinstance(at, time) for at in config[CONF_AT]):
            node.update(
                status=TriggerStatus.SCHEDULED,
                next=min(_next_time(at, weekdays, now) for at in config[CONF_AT]),
            )
            return node

    if (as_condition := _TRIGGER_AS_CONDITION.get(platform)) is None or (
        condition := as_condition.to_condition(config)
    ) is None:
        node["status"] = TriggerStatus.WAITS_FOR_EVENT
        return node

    try:
        condition = await condition_helper.async_validate_condition_config(
            hass, condition
        )
    except (probatio.Invalid, HomeAssistantError) as err:
        node.update(status=TriggerStatus.ERROR, error=str(err))
        return node
    leaf = await _async_evaluate_leaf(hass, condition, variables)
    node["status"] = {
        ConditionResult.PASS: as_condition.passed,
        ConditionResult.FAIL: as_condition.failed,
    }.get(leaf.pop("result"), TriggerStatus.ERROR)
    node.update(leaf)
    return node


def _verdict(
    data: DryRunInput, conditions_result: ConditionResult
) -> DryRunReason | None:
    """Return why the automation would not run now, None if it would."""
    if not data.enabled:
        return DryRunReason.AUTOMATION_OFF
    if conditions_result is ConditionResult.FAIL:
        return DryRunReason.CONDITIONS_NOT_MET
    if conditions_result is ConditionResult.ERROR:
        return DryRunReason.CONDITION_ERROR
    if conditions_result is ConditionResult.DEPENDS_ON_TRIGGER:
        return DryRunReason.DEPENDS_ON_TRIGGER
    if data.mode == SCRIPT_MODE_SINGLE and data.current_runs:
        return DryRunReason.ALREADY_RUNNING
    if data.max_runs is not None and data.current_runs >= data.max_runs:
        return DryRunReason.MAX_RUNS_REACHED
    return None


async def async_dry_run(hass: HomeAssistant, data: DryRunInput) -> dict[str, Any]:
    """Evaluate the triggers and conditions of an automation without acting."""
    trigger_names = _trigger_dependent_names(data.variables)
    variables, variables_error = _render_variables(hass, data, trigger_names)

    triggers = [
        await _async_evaluate_trigger(hass, index, config, variables)
        for index, config in enumerate(data.trigger_config)
    ]
    conditions = [
        await _async_evaluate_condition(
            hass, config, variables, f"condition/{index}", trigger_names
        )
        for index, config in enumerate(data.condition_config)
    ]
    conditions_result = _combine("and", (node["result"] for node in conditions))
    reason = _verdict(data, conditions_result)

    result: dict[str, Any] = {
        "enabled": data.enabled,
        "mode": data.mode,
        "current_runs": data.current_runs,
        "max_runs": data.max_runs,
        "would_run": (
            None if reason is DryRunReason.DEPENDS_ON_TRIGGER else reason is None
        ),
        "reason": reason,
        "triggers": triggers,
        "conditions_result": conditions_result,
        "conditions": conditions,
    }
    if variables_error is not None:
        result["variables_error"] = variables_error
    return result
