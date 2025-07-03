"""Offer reusable conditions."""

from __future__ import annotations

import abc
import asyncio
from collections import deque
from collections.abc import Callable, Container, Coroutine, Generator, Iterable
from contextlib import contextmanager
from datetime import datetime, time as dt_time, timedelta
import functools as ft
import logging
import re
import sys
from typing import TYPE_CHECKING, Any, Protocol, cast

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
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
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    CONF_WEEKDAY,
    CONF_ZONE,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_ANY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    WEEKDAYS,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    ConditionErrorMessage,
    HomeAssistantError,
    TemplateError,
)
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integrations,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.yaml import load_yaml_dict
from homeassistant.util.yaml.loader import JSON_TYPE

from . import config_validation as cv, entity_registry as er
from .integration_platform import async_process_integration_platforms
from .template import Template, render_complex
from .trace import (
    TraceElement,
    trace_append_element,
    trace_path,
    trace_path_get,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
)
from .typing import ConfigType, TemplateVarsType

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
    "zone": None,
}

INPUT_ENTITY_ID = re.compile(
    r"^input_(?:select|text|number|boolean|datetime)\.(?!.+__)(?!_)[\da-z_]+(?<!_)$"
)


CONDITION_DESCRIPTION_CACHE: HassKey[dict[str, dict[str, Any] | None]] = HassKey(
    "condition_description_cache"
)
CONDITION_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("condition_platform_subscriptions")
CONDITIONS: HassKey[dict[str, str]] = HassKey("conditions")


# Basic schemas to sanity check the condition descriptions,
# full validation is done by hassfest.conditions
_FIELD_SCHEMA = vol.Schema(
    {},
    extra=vol.ALLOW_EXTRA,
)

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Optional("fields"): vol.Schema({str: _FIELD_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise vol.Invalid("Key does not start with .")
    return key


_CONDITIONS_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, starts_with_dot)): object,
        cv.slug: vol.Any(None, _CONDITION_SCHEMA),
    }
)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the condition helper."""
    hass.data[CONDITION_DESCRIPTION_CACHE] = {}
    hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS] = []
    hass.data[CONDITIONS] = {}
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
    """Register a condition platform."""

    new_conditions: set[str] = set()

    if hasattr(platform, "async_get_conditions"):
        for condition_key in await platform.async_get_conditions(hass):
            hass.data[CONDITIONS][condition_key] = integration_domain
            new_conditions.add(condition_key)
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


class Condition(abc.ABC):
    """Condition class."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize condition."""

    @classmethod
    @abc.abstractmethod
    async def async_validate_condition_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    @abc.abstractmethod
    async def async_condition_from_config(self) -> ConditionCheckerType:
        """Evaluate state based on configuration."""


class ConditionProtocol(Protocol):
    """Define the format of condition modules."""

    async def async_get_conditions(
        self, hass: HomeAssistant
    ) -> dict[str, type[Condition]]:
        """Return the conditions provided by this integration."""


type ConditionCheckerType = Callable[[HomeAssistant, TemplateVarsType], bool | None]


def condition_trace_append(variables: TemplateVarsType, path: str) -> TraceElement:
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element)
    return trace_element


def condition_trace_set_result(result: bool, **kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.set_result(result=result, **kwargs)


def condition_trace_update_result(**kwargs: Any) -> None:
    """Update the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.update_result(**kwargs)


@contextmanager
def trace_condition(variables: TemplateVarsType) -> Generator[TraceElement]:
    """Trace condition evaluation."""
    should_pop = True
    trace_element = trace_stack_top(trace_stack_cv)
    if trace_element and trace_element.reuse_by_child:
        should_pop = False
        trace_element.reuse_by_child = False
    else:
        trace_element = condition_trace_append(variables, trace_path_get())
        trace_stack_push(trace_stack_cv, trace_element)
    try:
        yield trace_element
    except Exception as ex:
        trace_element.set_error(ex)
        raise
    finally:
        if should_pop:
            trace_stack_pop(trace_stack_cv)


def trace_condition_function(condition: ConditionCheckerType) -> ConditionCheckerType:
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
    hass: HomeAssistant, config: ConfigType
) -> ConditionProtocol | None:
    condition_key: str = config[CONF_CONDITION]
    platform_and_sub_type = condition_key.partition(".")
    platform: str | None = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    if platform is None:
        return None
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise HomeAssistantError(
            f'Invalid condition "{condition_key}" specified {config}'
        ) from None
    try:
        return await integration.async_get_platform("condition")
    except ImportError:
        raise HomeAssistantError(
            f"Integration '{platform}' does not provide condition support"
        ) from None


async def async_from_config(
    hass: HomeAssistant,
    config: ConfigType,
) -> ConditionCheckerType:
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

            @trace_condition_function
            def disabled_condition(
                hass: HomeAssistant, variables: TemplateVarsType = None
            ) -> bool | None:
                """Condition not enabled, will act as if it didn't exist."""
                return None

            return disabled_condition

    condition: str = config[CONF_CONDITION]
    factory: Any = None
    platform = await _async_get_condition_platform(hass, config)

    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        condition_instance = condition_descriptors[condition](hass, config)
        return await condition_instance.async_condition_from_config()

    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(sys.modules[__name__], fmt.format(condition), None)

        if factory:
            break

    # Check for partials to properly determine if coroutine function
    check_factory = factory
    while isinstance(check_factory, ft.partial):
        check_factory = check_factory.func

    if asyncio.iscoroutinefunction(check_factory):
        return cast(ConditionCheckerType, await factory(hass, config))
    return cast(ConditionCheckerType, factory(config))


async def async_and_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Create multi condition matcher using 'AND'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]

    @trace_condition_function
    def if_and_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test and condition."""
        errors = []
        for index, check in enumerate(checks):
            try:
                with trace_path(["conditions", str(index)]):
                    if check(hass, variables) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex("and", index=index, total=len(checks), error=ex)
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("and", errors=errors)

        return True

    return if_and_condition


async def async_or_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Create multi condition matcher using 'OR'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]

    @trace_condition_function
    def if_or_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test or condition."""
        errors = []
        for index, check in enumerate(checks):
            try:
                with trace_path(["conditions", str(index)]):
                    if check(hass, variables) is True:
                        return True
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex("or", index=index, total=len(checks), error=ex)
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("or", errors=errors)

        return False

    return if_or_condition


async def async_not_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Create multi condition matcher using 'NOT'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]

    @trace_condition_function
    def if_not_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test not condition."""
        errors = []
        for index, check in enumerate(checks):
            try:
                with trace_path(["conditions", str(index)]):
                    if check(hass, variables):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex("not", index=index, total=len(checks), error=ex)
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("not", errors=errors)

        return True

    return if_not_condition


def numeric_state(
    hass: HomeAssistant,
    entity: str | State | None,
    below: float | str | None = None,
    above: float | str | None = None,
    value_template: Template | None = None,
    variables: TemplateVarsType = None,
) -> bool:
    """Test a numeric state condition."""
    return run_callback_threadsafe(
        hass.loop,
        async_numeric_state,
        hass,
        entity,
        below,
        above,
        value_template,
        variables,
    ).result()


def async_numeric_state(
    hass: HomeAssistant,
    entity: str | State | None,
    below: float | str | None = None,
    above: float | str | None = None,
    value_template: Template | None = None,
    variables: TemplateVarsType = None,
    attribute: str | None = None,
) -> bool:
    """Test a numeric state condition."""
    if entity is None:
        raise ConditionErrorMessage("numeric_state", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("numeric_state", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        condition_trace_set_result(
            False,
            message=f"attribute '{attribute}' of entity {entity_id} does not exist",
        )
        return False

    value: Any = None
    if value_template is None:
        if attribute is None:
            value = entity.state
        else:
            value = entity.attributes.get(attribute)
    else:
        variables = dict(variables or {})
        variables["state"] = entity
        try:
            value = value_template.async_render(variables)
        except TemplateError as ex:
            raise ConditionErrorMessage(
                "numeric_state", f"template error: {ex}"
            ) from ex

    # Known states or attribute values that never match the numeric condition
    if value in (None, STATE_UNAVAILABLE, STATE_UNKNOWN):
        condition_trace_set_result(
            False,
            message=f"value '{value}' is non-numeric and treated as False",
        )
        return False

    try:
        fvalue = float(value)
    except (ValueError, TypeError) as ex:
        raise ConditionErrorMessage(
            "numeric_state",
            f"entity {entity_id} state '{value}' cannot be processed as a number",
        ) from ex

    if below is not None:
        if isinstance(below, str):
            if not (below_entity := hass.states.get(below)):
                raise ConditionErrorMessage(
                    "numeric_state", f"unknown 'below' entity {below}"
                )
            if below_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                return False
            try:
                if fvalue >= float(below_entity.state):
                    condition_trace_set_result(
                        False,
                        state=fvalue,
                        wanted_state_below=float(below_entity.state),
                    )
                    return False
            except (ValueError, TypeError) as ex:
                raise ConditionErrorMessage(
                    "numeric_state",
                    (
                        f"the 'below' entity {below} state '{below_entity.state}'"
                        " cannot be processed as a number"
                    ),
                ) from ex
        elif fvalue >= below:
            condition_trace_set_result(False, state=fvalue, wanted_state_below=below)
            return False

    if above is not None:
        if isinstance(above, str):
            if not (above_entity := hass.states.get(above)):
                raise ConditionErrorMessage(
                    "numeric_state", f"unknown 'above' entity {above}"
                )
            if above_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                return False
            try:
                if fvalue <= float(above_entity.state):
                    condition_trace_set_result(
                        False,
                        state=fvalue,
                        wanted_state_above=float(above_entity.state),
                    )
                    return False
            except (ValueError, TypeError) as ex:
                raise ConditionErrorMessage(
                    "numeric_state",
                    (
                        f"the 'above' entity {above} state '{above_entity.state}'"
                        " cannot be processed as a number"
                    ),
                ) from ex
        elif fvalue <= above:
            condition_trace_set_result(False, state=fvalue, wanted_state_above=above)
            return False

    condition_trace_set_result(True, state=fvalue)
    return True


def async_numeric_state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    attribute = config.get(CONF_ATTRIBUTE)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    @trace_condition_function
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


def state(
    hass: HomeAssistant,
    entity: str | State | None,
    req_state: Any,
    for_period: timedelta | None = None,
    attribute: str | None = None,
    variables: TemplateVarsType = None,
) -> bool:
    """Test if state matches requirements.

    Async friendly.
    """
    if entity is None:
        raise ConditionErrorMessage("state", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("state", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        condition_trace_set_result(
            False,
            message=f"attribute '{attribute}' of entity {entity_id} does not exist",
        )
        return False

    assert isinstance(entity, State)

    if attribute is None:
        value: Any = entity.state
    else:
        value = entity.attributes.get(attribute)

    if not isinstance(req_state, list):
        req_state = [req_state]

    is_state = False
    for req_state_value in req_state:
        state_value = req_state_value
        if (
            isinstance(req_state_value, str)
            and INPUT_ENTITY_ID.match(req_state_value) is not None
        ):
            if not (state_entity := hass.states.get(req_state_value)):
                raise ConditionErrorMessage(
                    "state", f"the 'state' entity {req_state_value} is unavailable"
                )
            state_value = state_entity.state
        is_state = value == state_value
        if is_state:
            break

    if for_period is None or not is_state:
        condition_trace_set_result(is_state, state=value, wanted_state=state_value)
        return is_state

    try:
        for_period = cv.positive_time_period(render_complex(for_period, variables))
    except TemplateError as ex:
        raise ConditionErrorMessage("state", f"template error: {ex}") from ex
    except vol.Invalid as ex:
        raise ConditionErrorMessage("state", f"schema error: {ex}") from ex

    duration = dt_util.utcnow() - cast(timedelta, for_period)
    duration_ok = duration > entity.last_changed
    condition_trace_set_result(duration_ok, state=value, duration=duration)
    return duration_ok


def state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    req_states: str | list[str] = config.get(CONF_STATE, [])
    for_period = config.get(CONF_FOR)
    attribute = config.get(CONF_ATTRIBUTE)
    match = config.get(CONF_MATCH, ENTITY_MATCH_ALL)

    if not isinstance(req_states, list):
        req_states = [req_states]

    @trace_condition_function
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


def template(
    hass: HomeAssistant, value_template: Template, variables: TemplateVarsType = None
) -> bool:
    """Test if template condition matches."""
    return run_callback_threadsafe(
        hass.loop, async_template, hass, value_template, variables
    ).result()


def async_template(
    hass: HomeAssistant,
    value_template: Template,
    variables: TemplateVarsType = None,
    trace_result: bool = True,
) -> bool:
    """Test if template condition matches."""
    try:
        info = value_template.async_render_to_info(variables, parse_result=False)
        value = info.result()
    except TemplateError as ex:
        raise ConditionErrorMessage("template", str(ex)) from ex

    result = value.lower() == "true"
    if trace_result:
        condition_trace_set_result(result, entities=list(info.entities))
    return result


def async_template_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    value_template = cast(Template, config.get(CONF_VALUE_TEMPLATE))

    @trace_condition_function
    def template_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate template based if-condition."""
        return async_template(hass, value_template, variables)

    return template_if


def time(
    hass: HomeAssistant,
    before: dt_time | str | None = None,
    after: dt_time | str | None = None,
    weekday: str | Container[str] | None = None,
) -> bool:
    """Test if local time condition matches.

    Handle the fact that time is continuous and we may be testing for
    a period that crosses midnight. In that case it is easier to test
    for the opposite. "(23:59 <= now < 00:01)" would be the same as
    "not (00:01 <= now < 23:59)".
    """
    from homeassistant.components.sensor import SensorDeviceClass  # noqa: PLC0415

    now = dt_util.now()
    now_time = now.time()

    if after is None:
        after = dt_time(0)
    elif isinstance(after, str):
        if not (after_entity := hass.states.get(after)):
            raise ConditionErrorMessage("time", f"unknown 'after' entity {after}")
        if after_entity.domain == "input_datetime":
            after = dt_time(
                after_entity.attributes.get("hour", 23),
                after_entity.attributes.get("minute", 59),
                after_entity.attributes.get("second", 59),
            )
        elif after_entity.domain == "time" and after_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            after = datetime.strptime(after_entity.state, "%H:%M:%S").time()
        elif (
            after_entity.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.TIMESTAMP
        ) and after_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            after_datetime = dt_util.parse_datetime(after_entity.state)
            if after_datetime is None:
                return False
            after = dt_util.as_local(after_datetime).time()
        else:
            return False

    if before is None:
        before = dt_time(23, 59, 59, 999999)
    elif isinstance(before, str):
        if not (before_entity := hass.states.get(before)):
            raise ConditionErrorMessage("time", f"unknown 'before' entity {before}")
        if before_entity.domain == "input_datetime":
            before = dt_time(
                before_entity.attributes.get("hour", 23),
                before_entity.attributes.get("minute", 59),
                before_entity.attributes.get("second", 59),
            )
        elif before_entity.domain == "time":
            try:
                before = datetime.strptime(before_entity.state, "%H:%M:%S").time()
            except ValueError:
                return False
        elif (
            before_entity.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.TIMESTAMP
        ) and before_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            before_timedatime = dt_util.parse_datetime(before_entity.state)
            if before_timedatime is None:
                return False
            before = dt_util.as_local(before_timedatime).time()
        else:
            return False

    if after < before:
        condition_trace_update_result(after=after, now_time=now_time, before=before)
        if not after <= now_time < before:
            return False
    else:
        condition_trace_update_result(after=after, now_time=now_time, before=before)
        if before <= now_time < after:
            return False

    if weekday is not None:
        now_weekday = WEEKDAYS[now.weekday()]

        condition_trace_update_result(weekday=weekday, now_weekday=now_weekday)
        if (
            isinstance(weekday, str) and weekday != now_weekday
        ) or now_weekday not in weekday:
            return False

    return True


def time_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with time based condition."""
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    @trace_condition_function
    def time_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return time(hass, before, after, weekday)

    return time_if


def zone(
    hass: HomeAssistant,
    zone_ent: str | State | None,
    entity: str | State | None,
) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
    from homeassistant.components import zone as zone_cmp  # noqa: PLC0415

    if zone_ent is None:
        raise ConditionErrorMessage("zone", "no zone specified")

    if isinstance(zone_ent, str):
        zone_ent_id = zone_ent

        if (zone_ent := hass.states.get(zone_ent)) is None:
            raise ConditionErrorMessage("zone", f"unknown zone {zone_ent_id}")

    if entity is None:
        raise ConditionErrorMessage("zone", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("zone", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if entity.state in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        return False

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None:
        raise ConditionErrorMessage(
            "zone", f"entity {entity_id} has no 'latitude' attribute"
        )

    if longitude is None:
        raise ConditionErrorMessage(
            "zone", f"entity {entity_id} has no 'longitude' attribute"
        )

    return zone_cmp.in_zone(
        zone_ent, latitude, longitude, entity.attributes.get(ATTR_GPS_ACCURACY, 0)
    )


def zone_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with zone based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    zone_entity_ids = config.get(CONF_ZONE, [])

    @trace_condition_function
    def if_in_zone(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        errors = []

        all_ok = True
        for entity_id in entity_ids:
            entity_ok = False
            for zone_entity_id in zone_entity_ids:
                try:
                    if zone(hass, zone_entity_id, entity_id):
                        entity_ok = True
                except ConditionErrorMessage as ex:
                    errors.append(
                        ConditionErrorMessage(
                            "zone",
                            (
                                f"error matching {entity_id} with {zone_entity_id}:"
                                f" {ex.message}"
                            ),
                        )
                    )

            if not entity_ok:
                all_ok = False

        # Raise the errors only if no definitive result was found
        if errors and not all_ok:
            raise ConditionErrorContainer("zone", errors=errors)

        return all_ok

    return if_in_zone


async def async_trigger_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Test a trigger condition."""
    trigger_id = config[CONF_ID]

    @trace_condition_function
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
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    condition: str = config[CONF_CONDITION]
    if condition in ("and", "not", "or"):
        conditions = []
        for sub_cond in config["conditions"]:
            sub_cond = await async_validate_condition_config(hass, sub_cond)
            conditions.append(sub_cond)
        config["conditions"] = conditions
        return config

    platform = await _async_get_condition_platform(hass, config)
    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        if not (condition_class := condition_descriptors.get(condition)):
            raise vol.Invalid(f"Invalid condition '{condition}' specified")
        return await condition_class.async_validate_condition_config(hass, config)
    if platform is None and condition in ("numeric_state", "state"):
        validator = cast(
            Callable[[HomeAssistant, ConfigType], ConfigType],
            getattr(sys.modules[__name__], VALIDATE_CONFIG_FORMAT.format(condition)),
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
) -> Callable[[TemplateVarsType], bool]:
    """AND all conditions."""
    checks: list[ConditionCheckerType] = [
        await async_from_config(hass, condition_config)
        for condition_config in condition_configs
    ]

    def check_conditions(variables: TemplateVarsType = None) -> bool:
        """AND all conditions."""
        errors: list[ConditionErrorIndex] = []
        for index, check in enumerate(checks):
            try:
                with trace_path(["condition", str(index)]):
                    if check(hass, variables) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "condition", index=index, total=len(checks), error=ex
                    )
                )

        if errors:
            logger.warning(
                "Error evaluating condition in '%s':\n%s",
                name,
                ConditionErrorContainer("condition", errors=errors),
            )
            return False

        return True

    return check_conditions


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

        entity_ids = config.get(CONF_ENTITY_ID)

        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        if entity_ids is not None:
            referenced.update(entity_ids)

    return referenced


@callback
def async_extract_devices(config: ConfigType | Template) -> set[str]:
    """Extract devices from a condition."""
    referenced = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if condition != "device":
            continue

        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            referenced.add(device_id)

    return referenced


def _load_conditions_file(hass: HomeAssistant, integration: Integration) -> JSON_TYPE:
    """Load conditions file for an integration."""
    try:
        return cast(
            JSON_TYPE,
            _CONDITIONS_SCHEMA(
                load_yaml_dict(str(integration.file_path / "conditions.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find conditions.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, vol.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse conditions.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_conditions_files(
    hass: HomeAssistant, integrations: Iterable[Integration]
) -> dict[str, JSON_TYPE]:
    """Load condition files for multiple integrations."""
    return {
        integration.domain: _load_conditions_file(hass, integration)
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all conditions."""
    descriptions_cache = hass.data[CONDITION_DESCRIPTION_CACHE]

    conditions = hass.data[CONDITIONS]
    # See if there are new conditions not seen before.
    # Any condition that we saw before already has an entry in description_cache.
    all_conditions = set(conditions)
    previous_all_conditions = set(descriptions_cache)
    # If the conditions are the same, we can return the cache
    if previous_all_conditions == all_conditions:
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_conditions_descriptions: dict[str, JSON_TYPE] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new conditions get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    conditions = conditions.copy()

    if missing_conditions := all_conditions.difference(descriptions_cache):
        domains_with_missing_conditions = {
            conditions[missing_condition] for missing_condition in missing_conditions
        }
        ints_or_excs = await async_get_integrations(
            hass, domains_with_missing_conditions
        )
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_conditions:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.debug(
                "Failed to load conditions.yaml for integration: %s",
                domain,
                exc_info=int_or_exc,
            )

        if integrations:
            new_conditions_descriptions = await hass.async_add_executor_job(
                _load_conditions_files, hass, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_condition in missing_conditions:
        domain = conditions[missing_condition]

        if (
            yaml_description := new_conditions_descriptions.get(domain, {}).get(  # type: ignore[union-attr]
                missing_condition
            )
        ) is None:
            _LOGGER.debug(
                "No condition descriptions found for condition %s, skipping",
                missing_condition,
            )
            new_descriptions_cache[missing_condition] = None
            continue

        description = {"fields": yaml_description.get("fields", {})}

        new_descriptions_cache[missing_condition] = description

    hass.data[CONDITION_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache
