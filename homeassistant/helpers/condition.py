"""Offer reusable conditions."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Container, Generator
from contextlib import contextmanager
from datetime import datetime, time as dt_time, timedelta
import functools as ft
import re
import sys
from typing import Any, Protocol, cast

import voluptuous as vol

from homeassistant.components import zone as zone_cmp
from homeassistant.components.sensor import SensorDeviceClass
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
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
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
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.async_ import run_callback_threadsafe
import homeassistant.util.dt as dt_util

from . import config_validation as cv, entity_registry as er
from .sun import get_astral_event_date
from .template import Template, attach as template_attach, render_complex
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

_PLATFORM_ALIASES = {
    "and": None,
    "device": "device_automation",
    "not": None,
    "numeric_state": None,
    "or": None,
    "state": None,
    "sun": None,
    "template": None,
    "time": None,
    "trigger": None,
    "zone": None,
}

INPUT_ENTITY_ID = re.compile(
    r"^input_(?:select|text|number|boolean|datetime)\.(?!.+__)(?!_)[\da-z_]+(?<!_)$"
)


class ConditionProtocol(Protocol):
    """Define the format of device_condition modules.

    Each module must define either CONDITION_SCHEMA or async_validate_condition_config.
    """

    CONDITION_SCHEMA: vol.Schema

    async def async_validate_condition_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    def async_condition_from_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> ConditionCheckerType:
        """Evaluate state based on configuration."""


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
def trace_condition(variables: TemplateVarsType) -> Generator[TraceElement, None, None]:
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
    platform = config[CONF_CONDITION]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    if platform is None:
        return None
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise HomeAssistantError(
            f'Invalid condition "{platform}" specified {config}'
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
    factory: Any = None
    platform = await _async_get_condition_platform(hass, config)

    if platform is None:
        condition = config.get(CONF_CONDITION)
        for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
            factory = getattr(sys.modules[__name__], fmt.format(condition), None)

            if factory:
                break
    else:
        factory = platform.async_condition_from_config

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
    entity: None | str | State,
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
    entity: None | str | State,
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
        if value_template is not None:
            value_template.hass = hass

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
    entity: None | str | State,
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
        template_attach(hass, for_period)
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


def sun(
    hass: HomeAssistant,
    before: str | None = None,
    after: str | None = None,
    before_offset: timedelta | None = None,
    after_offset: timedelta | None = None,
) -> bool:
    """Test if current time matches sun requirements."""
    utcnow = dt_util.utcnow()
    today = dt_util.as_local(utcnow).date()
    before_offset = before_offset or timedelta(0)
    after_offset = after_offset or timedelta(0)

    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, today)
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)

    has_sunrise_condition = SUN_EVENT_SUNRISE in (before, after)
    has_sunset_condition = SUN_EVENT_SUNSET in (before, after)

    after_sunrise = today > dt_util.as_local(cast(datetime, sunrise)).date()
    if after_sunrise and has_sunrise_condition:
        tomorrow = today + timedelta(days=1)
        sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, tomorrow)

    after_sunset = today > dt_util.as_local(cast(datetime, sunset)).date()
    if after_sunset and has_sunset_condition:
        tomorrow = today + timedelta(days=1)
        sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, tomorrow)

    # Special case: before sunrise OR after sunset
    # This will handle the very rare case in the polar region when the sun rises/sets
    # but does not set/rise.
    # However this entire condition does not handle those full days of darkness
    # or light, the following should be used instead:
    #
    #    condition:
    #      condition: state
    #      entity_id: sun.sun
    #      state: 'above_horizon' (or 'below_horizon')
    #
    if before == SUN_EVENT_SUNRISE and after == SUN_EVENT_SUNSET:
        wanted_time_before = cast(datetime, sunrise) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        wanted_time_after = cast(datetime, sunset) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        return utcnow < wanted_time_before or utcnow > wanted_time_after

    if sunrise is None and has_sunrise_condition:
        # There is no sunrise today
        condition_trace_set_result(False, message="no sunrise today")
        return False

    if sunset is None and has_sunset_condition:
        # There is no sunset today
        condition_trace_set_result(False, message="no sunset today")
        return False

    if before == SUN_EVENT_SUNRISE:
        wanted_time_before = cast(datetime, sunrise) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        if utcnow > wanted_time_before:
            return False

    if before == SUN_EVENT_SUNSET:
        wanted_time_before = cast(datetime, sunset) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        if utcnow > wanted_time_before:
            return False

    if after == SUN_EVENT_SUNRISE:
        wanted_time_after = cast(datetime, sunrise) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        if utcnow < wanted_time_after:
            return False

    if after == SUN_EVENT_SUNSET:
        wanted_time_after = cast(datetime, sunset) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        if utcnow < wanted_time_after:
            return False

    return True


def sun_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with sun based condition."""
    before = config.get("before")
    after = config.get("after")
    before_offset = config.get("before_offset")
    after_offset = config.get("after_offset")

    @trace_condition_function
    def sun_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return sun(hass, before, after, before_offset, after_offset)

    return sun_if


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
        value_template.hass = hass

        return async_template(hass, value_template, variables)

    return template_if


def time(
    hass: HomeAssistant,
    before: dt_time | str | None = None,
    after: dt_time | str | None = None,
    weekday: None | str | Container[str] = None,
) -> bool:
    """Test if local time condition matches.

    Handle the fact that time is continuous and we may be testing for
    a period that crosses midnight. In that case it is easier to test
    for the opposite. "(23:59 <= now < 00:01)" would be the same as
    "not (00:01 <= now < 23:59)".
    """
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
        elif after_entity.attributes.get(
            ATTR_DEVICE_CLASS
        ) == SensorDeviceClass.TIMESTAMP and after_entity.state not in (
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
        elif before_entity.attributes.get(
            ATTR_DEVICE_CLASS
        ) == SensorDeviceClass.TIMESTAMP and before_entity.state not in (
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
            isinstance(weekday, str)
            and weekday != now_weekday
            or now_weekday not in weekday
        ):
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
    zone_ent: None | str | State,
    entity: None | str | State,
) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
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
    condition = config[CONF_CONDITION]
    if condition in ("and", "not", "or"):
        conditions = []
        for sub_cond in config["conditions"]:
            sub_cond = await async_validate_condition_config(hass, sub_cond)
            conditions.append(sub_cond)
        config["conditions"] = conditions
        return config

    platform = await _async_get_condition_platform(hass, config)
    if platform is not None and hasattr(platform, "async_validate_condition_config"):
        return await platform.async_validate_condition_config(hass, config)
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
