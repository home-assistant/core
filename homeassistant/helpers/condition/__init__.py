"""Offer reusable conditions."""

from collections import deque
from collections.abc import Callable, Coroutine
import functools as ft
import inspect
import logging
import sys
from typing import Any, Literal, Protocol, cast, overload

import probatio

from homeassistant.const import (
    CONF_ABOVE,
    CONF_AFTER,
    CONF_ATTRIBUTE,
    CONF_BEFORE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_ID,
    CONF_MATCH,
    CONF_OPTIONS,
    CONF_STATE,
    CONF_TARGET,
    CONF_VALUE_TEMPLATE,
    CONF_WEEKDAY,
    CONF_ZONE,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_ANY,
)
from homeassistant.core import HomeAssistant, callback, valid_entity_id
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    HomeAssistantError,
    TemplateError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.automation import (
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.trace import trace_path
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.hass_dict import HassKey

from .conditions import (
    AndConditionChecker,
    CompoundConditionChecker,
    DisabledConditionChecker,
    LegacyConditionChecker,
    NotConditionChecker,
    OrConditionChecker,
    async_numeric_state,
    async_template,
    numeric_state,
    state,
    template,
    time,
)
from .descriptions import (
    CONDITION_DESCRIPTION_CACHE,
    async_get_all_descriptions,
    starts_with_dot,
)
from .entity_condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    DATA_HISTORY_PRIMING_MANAGER,
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    HISTORY_PRIMING_TIMEOUT,
    MAX_HISTORY_PRIMING_LOOKBACK,
    NUMERICAL_CONDITION_SCHEMA,
    EntityConditionBase,
    EntityNumericalConditionBase,
    EntityNumericalConditionWithUnitBase,
    EntityStateConditionBase,
    HistoryPrimingManager,
    make_entity_numerical_condition,
    make_entity_numerical_condition_with_unit,
    make_entity_state_condition,
)
from .models import (
    CONDITION_BASE_SCHEMA,
    CONDITIONS,
    Condition,
    ConditionChecker,
    ConditionCheckerType,
    ConditionCheckerTypeOptional,
    ConditionCheckParams,
    ConditionConfig,
    ConditionsChecker,
)
from .tracing import (
    condition_trace_append,
    condition_trace_set_result,
    condition_trace_update_result,
    trace_condition,
)

__all__ = [
    "ASYNC_FROM_CONFIG_FORMAT",
    "ATTR_BEHAVIOR",
    "BEHAVIOR_ALL",
    "BEHAVIOR_ANY",
    "CONDITIONS",
    "CONDITION_DESCRIPTION_CACHE",
    "CONDITION_PLATFORM_SUBSCRIPTIONS",
    "ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL",
    "FROM_CONFIG_FORMAT",
    "HISTORY_PRIMING_TIMEOUT",
    "MAX_HISTORY_PRIMING_LOOKBACK",
    "NUMERICAL_CONDITION_SCHEMA",
    "VALIDATE_CONFIG_FORMAT",
    "AndConditionChecker",
    "CompoundConditionChecker",
    "Condition",
    "ConditionCheckParams",
    "ConditionChecker",
    "ConditionCheckerType",
    "ConditionCheckerTypeOptional",
    "ConditionConfig",
    "ConditionProtocol",
    "ConditionsChecker",
    "DisabledConditionChecker",
    "EntityConditionBase",
    "EntityNumericalConditionBase",
    "EntityNumericalConditionWithUnitBase",
    "EntityStateConditionBase",
    "LegacyConditionChecker",
    "NotConditionChecker",
    "OrConditionChecker",
    "async_and_from_config",
    "async_conditions_from_config",
    "async_extract_devices",
    "async_extract_entities",
    "async_extract_targets",
    "async_from_config",
    "async_get_all_descriptions",
    "async_not_from_config",
    "async_numeric_state",
    "async_numeric_state_from_config",
    "async_or_from_config",
    "async_setup",
    "async_subscribe_platform_events",
    "async_template",
    "async_template_from_config",
    "async_trigger_from_config",
    "async_validate_condition_config",
    "async_validate_conditions_config",
    "condition_trace_append",
    "condition_trace_set_result",
    "condition_trace_update_result",
    "make_entity_numerical_condition",
    "make_entity_numerical_condition_with_unit",
    "make_entity_state_condition",
    "numeric_state",
    "numeric_state_validate_config",
    "starts_with_dot",
    "state",
    "state_from_config",
    "state_validate_config",
    "template",
    "time",
    "time_from_config",
    "trace_condition",
    "trace_condition_function",
]

ASYNC_FROM_CONFIG_FORMAT = "async_{}_from_config"
FROM_CONFIG_FORMAT = "{}_from_config"
VALIDATE_CONFIG_FORMAT = "{}_validate_config"

_LOGGER = logging.getLogger(__name__)


_PLATFORM_ALIASES: dict[str | None, str | None] = {
    "and": None,
    "device": "device_automation",
    "not": None,
    "numeric_state": None,
    "or": None,
    "state": None,
    "template": None,
    "time": None,
    "trigger": None,
}


CONDITION_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("condition_platform_subscriptions")


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the condition helper."""
    hass.data[CONDITION_DESCRIPTION_CACHE] = {}
    hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS] = []
    hass.data[CONDITIONS] = {}
    hass.data[DATA_HISTORY_PRIMING_MANAGER] = HistoryPrimingManager(hass)

    await async_process_integration_platforms(
        hass, "condition", _register_condition_platform, wait_for_platforms=True
    )


@callback
def async_subscribe_platform_events(
    hass: HomeAssistant,
    on_event: Callable[[set[str]], Coroutine[Any, Any, None]],
) -> Callable[[], None]:
    """Subscribe to condition platform events."""
    condition_platform_event_subscriptions = hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS]

    def remove_subscription() -> None:
        condition_platform_event_subscriptions.remove(on_event)

    condition_platform_event_subscriptions.append(on_event)
    return remove_subscription


async def _register_condition_platform(
    hass: HomeAssistant, integration_domain: str, platform: ConditionProtocol
) -> None:
    """Register a condition platform and notify listeners.

    If the condition platform does not provide any conditions,
    listeners will not be notified.
    """
    new_conditions: set[str] = set()
    conditions = hass.data[CONDITIONS]

    if hasattr(platform, "async_get_conditions"):
        all_conditions = await platform.async_get_conditions(hass)
        for condition_key in all_conditions:
            condition_key = get_absolute_description_key(
                integration_domain, condition_key
            )
            if condition_key not in conditions:
                conditions[condition_key] = integration_domain
                new_conditions.add(condition_key)
        if not new_conditions:
            if not all_conditions:
                _LOGGER.debug(
                    "Integration %s returned no conditions in async_get_conditions",
                    integration_domain,
                )
            return
    else:
        _LOGGER.debug(
            "Integration %s does not provide condition support, skipping",
            integration_domain,
        )
        return

    # We don't use gather here because gather adds additional overhead
    # when wrapping each coroutine in a task, and we expect our listeners
    # to call condition.async_get_all_descriptions which will only yield
    # the first time it's called, after that it returns cached data.
    for listener in hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS]:
        try:
            await listener(new_conditions)
        except Exception:
            _LOGGER.exception("Error while notifying condition platform listener")


class ConditionProtocol(Protocol):
    """Define the format of condition modules."""

    async def async_get_conditions(
        self, hass: HomeAssistant
    ) -> dict[str, type[Condition]]:
        """Return the conditions provided by this integration."""


@overload
def trace_condition_function(
    condition: ConditionCheckerType,
) -> ConditionCheckerType: ...


@overload
def trace_condition_function(
    condition: ConditionCheckerTypeOptional,
) -> ConditionCheckerTypeOptional: ...


def trace_condition_function(
    condition: ConditionCheckerType | ConditionCheckerTypeOptional,
) -> ConditionCheckerType | ConditionCheckerTypeOptional:
    """Wrap a condition function to enable basic tracing."""

    @ft.wraps(condition)
    def wrapper(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool | None:
        """Trace condition."""
        with trace_condition(variables):
            result = condition(hass, variables)
            condition_trace_update_result(result=result)
            return result

    return wrapper


async def _async_get_condition_platform(
    hass: HomeAssistant, condition_key: str
) -> tuple[str, ConditionProtocol | None]:
    platform_and_sub_type = condition_key.split(".")
    platform: str | None = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    if platform is None:
        return "", None

    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise HomeAssistantError(
            f'Invalid condition "{condition_key}" specified'
        ) from None
    try:
        platform_module = await integration.async_get_platform("condition")
    except ImportError:
        raise HomeAssistantError(
            f"Integration '{platform}' does not provide condition support"
        ) from None

    # Ensure conditions are registered so descriptions can be loaded
    await _register_condition_platform(hass, platform, platform_module)

    return platform, platform_module


async def async_from_config(
    hass: HomeAssistant,
    config: ConfigType,
) -> ConditionChecker:
    """Turn a condition configuration into a method.

    Should be run on the event loop.
    """
    # Check if condition is not enabled
    if CONF_ENABLED in config:
        enabled = config[CONF_ENABLED]
        if isinstance(enabled, Template):
            try:
                enabled = enabled.async_render(limited=True)
            except TemplateError as err:
                raise HomeAssistantError(
                    f"Error rendering condition enabled template: {err}"
                ) from err
        if not enabled:
            disabled_checker = DisabledConditionChecker(hass)
            await disabled_checker.async_setup()
            return disabled_checker

    condition_key: str = config[CONF_CONDITION]
    factory: Any = None
    platform_domain, platform = await _async_get_condition_platform(hass, condition_key)

    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        relative_condition_key = get_relative_description_key(
            platform_domain, condition_key
        )
        condition_cls = condition_descriptors[relative_condition_key]
        condition = condition_cls(
            hass,
            ConditionConfig(
                options=config.get(CONF_OPTIONS),
                target=config.get(CONF_TARGET),
            ),
        )
        await condition.async_setup()
        return condition

    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(sys.modules[__name__], fmt.format(condition_key), None)

        if factory:
            break

    # Check for partials to properly determine if coroutine function
    check_factory = factory
    while isinstance(check_factory, ft.partial):
        check_factory = check_factory.func

    checker: ConditionChecker | ConditionCheckerType
    if inspect.iscoroutinefunction(check_factory):
        checker = await factory(hass, config)
    else:
        checker = factory(config)
    if not isinstance(checker, ConditionChecker):
        checker = LegacyConditionChecker(hass, checker)
    await checker.async_setup()
    return checker


async def async_and_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'AND'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return AndConditionChecker(hass, checks)


async def async_or_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'OR'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return OrConditionChecker(hass, checks)


async def async_not_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'NOT'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return NotConditionChecker(hass, checks)


def async_numeric_state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    attribute = config.get(CONF_ATTRIBUTE)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def if_numeric_state(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test numeric state condition."""
        errors = []
        for index, entity_id in enumerate(entity_ids):
            try:
                with trace_path(["entity_id", str(index)]), trace_condition(variables):
                    if not async_numeric_state(
                        hass,
                        entity_id,
                        below,
                        above,
                        value_template,
                        variables,
                        attribute,
                    ):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "numeric_state", index=index, total=len(entity_ids), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("numeric_state", errors=errors)

        return True

    return if_numeric_state


def state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    req_states: str | list[str] = config.get(CONF_STATE, [])
    for_period = config.get(CONF_FOR)
    attribute = config.get(CONF_ATTRIBUTE)
    match = config.get(CONF_MATCH, ENTITY_MATCH_ALL)

    if not isinstance(req_states, list):
        req_states = [req_states]

    def if_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        errors = []
        result: bool = match != ENTITY_MATCH_ANY
        for index, entity_id in enumerate(entity_ids):
            try:
                with trace_path(["entity_id", str(index)]), trace_condition(variables):
                    if state(
                        hass, entity_id, req_states, for_period, attribute, variables
                    ):
                        result = True
                    elif match == ENTITY_MATCH_ALL:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "state", index=index, total=len(entity_ids), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("state", errors=errors)

        return result

    return if_state


def async_template_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    value_template = cast(Template, config.get(CONF_VALUE_TEMPLATE))

    def template_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate template based if-condition."""
        return async_template(hass, value_template, variables)

    return template_if


def time_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with time based condition."""
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    def time_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return time(hass, before, after, weekday)

    return time_if


async def async_trigger_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Test a trigger condition."""
    trigger_id = config[CONF_ID]

    def trigger_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate trigger based if-condition."""
        return (
            variables is not None
            and "trigger" in variables
            and variables["trigger"].get("id") in trigger_id
        )

    return trigger_if


def numeric_state_validate_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate numeric_state condition config."""

    registry = er.async_get(hass)
    config = dict(config)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[CONF_ENTITY_ID])
    )
    return config


def state_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate state condition config."""

    registry = er.async_get(hass)
    config = dict(config)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[CONF_ENTITY_ID])
    )
    return config


async def async_validate_condition_config(
    hass: HomeAssistant, config: ConfigType | str
) -> ConfigType:
    """Validate config."""
    if isinstance(config, str):
        config = {
            CONF_CONDITION: "template",
            CONF_VALUE_TEMPLATE: cv.dynamic_template(config),
        }
    condition_key: str = config[CONF_CONDITION]

    if condition_key in ("and", "not", "or"):
        conditions = []
        for sub_cond in config["conditions"]:
            sub_cond = await async_validate_condition_config(hass, sub_cond)
            conditions.append(sub_cond)
        config["conditions"] = conditions
        return config

    platform_domain, platform = await _async_get_condition_platform(hass, condition_key)

    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        relative_condition_key = get_relative_description_key(
            platform_domain, condition_key
        )
        if not (condition_class := condition_descriptors.get(relative_condition_key)):
            raise probatio.Invalid(f"Invalid condition '{condition_key}' specified")
        return await condition_class.async_validate_complete_config(hass, config)

    config = move_options_fields_to_top_level(config, CONDITION_BASE_SCHEMA)

    if condition_key in ("numeric_state", "state"):
        validator = cast(
            Callable[[HomeAssistant, ConfigType], ConfigType],
            getattr(
                sys.modules[__name__], VALIDATE_CONFIG_FORMAT.format(condition_key)
            ),
        )
        return validator(hass, config)

    return config


async def async_validate_conditions_config(
    hass: HomeAssistant, conditions: list[ConfigType]
) -> list[ConfigType | Template]:
    """Validate config."""
    # No gather here because async_validate_condition_config is unlikely
    # to suspend and the overhead of creating many tasks is not worth it
    return [await async_validate_condition_config(hass, cond) for cond in conditions]


async def async_conditions_from_config(
    hass: HomeAssistant,
    condition_configs: list[ConfigType],
    logger: logging.Logger,
    name: str,
) -> ConditionsChecker:
    """AND all conditions."""
    checks = [
        await async_from_config(hass, condition_config)
        for condition_config in condition_configs
    ]
    return ConditionsChecker(checks, logger, name)


@callback
def async_extract_entities(config: ConfigType | Template) -> set[str]:
    """Extract entities from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if condition == "time":
            # The before and after options can be a time or an entity id.
            for key in (CONF_AFTER, CONF_BEFORE):
                if isinstance(value := config.get(key), str) and valid_entity_id(value):
                    referenced.add(value)
            continue

        if condition == "zone":
            options = config.get(CONF_OPTIONS, {})
            referenced.update(options.get(CONF_ENTITY_ID, []))
            referenced.update(options.get(CONF_ZONE, []))

        elif condition in (
            "zone.in_zone",
            "zone.not_in_zone",
            "zone.occupancy_is_detected",
            "zone.occupancy_is_not_detected",
        ):
            if zone_entity_id := config.get(CONF_OPTIONS, {}).get(CONF_ZONE):
                referenced.add(zone_entity_id)

        entity_ids = config.get(CONF_ENTITY_ID)

        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        if entity_ids is not None:
            referenced.update(entity_ids)

        if target_entities := _get_targets_from_condition_config(
            config, CONF_ENTITY_ID
        ):
            referenced.update(target_entities)

    return referenced


@callback
def async_extract_devices(config: ConfigType | Template) -> set[str]:
    """Extract devices from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if condition == "device":
            if (device_id := config.get(CONF_DEVICE_ID)) is not None:
                referenced.add(device_id)
            continue

        if target_devices := _get_targets_from_condition_config(config, CONF_DEVICE_ID):
            referenced.update(target_devices)

    return referenced


@callback
def async_extract_targets(
    config: ConfigType | Template,
    target_type: Literal["area_id", "floor_id", "label_id"],
) -> set[str]:
    """Extract targets from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if targets := _get_targets_from_condition_config(config, target_type):
            referenced.update(targets)
    return referenced


@callback
def _get_targets_from_condition_config(
    config: ConfigType,
    target: Literal["entity_id", "device_id", "area_id", "floor_id", "label_id"],
) -> list[str]:
    """Extract targets from a condition target config."""
    if not (target_conf := config.get(CONF_TARGET)):
        return []
    if not (targets := target_conf.get(target)):
        return []

    return [targets] if isinstance(targets, str) else targets
