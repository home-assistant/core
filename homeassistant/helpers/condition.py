"""Offer reusable conditions."""
import asyncio
from collections import deque
from datetime import datetime, timedelta
import functools as ft
import logging
import re
import sys
from typing import Any, Callable, Container, List, Optional, Set, Union, cast

from homeassistant.components import zone as zone_cmp
from homeassistant.components.device_automation import (
    async_get_device_automation_platform,
)
from homeassistant.const import (
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
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    CONF_WEEKDAY,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
    WEEKDAYS,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import ConditionError, HomeAssistantError, TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.async_ import run_callback_threadsafe
import homeassistant.util.dt as dt_util

FROM_CONFIG_FORMAT = "{}_from_config"
ASYNC_FROM_CONFIG_FORMAT = "async_{}_from_config"

_LOGGER = logging.getLogger(__name__)

INPUT_ENTITY_ID = re.compile(
    r"^input_(?:select|text|number|boolean|datetime)\.(?!.+__)(?!_)[\da-z_]+(?<!_)$"
)

ConditionCheckerType = Callable[[HomeAssistant, TemplateVarsType], bool]


async def async_from_config(
    hass: HomeAssistant,
    config: Union[ConfigType, Template],
    config_validation: bool = True,
) -> ConditionCheckerType:
    """Turn a condition configuration into a method.

    Should be run on the event loop.
    """
    if isinstance(config, Template):
        # We got a condition template, wrap it in a configuration to pass along.
        config = {
            CONF_CONDITION: "template",
            CONF_VALUE_TEMPLATE: config,
        }

    condition = config.get(CONF_CONDITION)
    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(sys.modules[__name__], fmt.format(condition), None)

        if factory:
            break

    if factory is None:
        raise HomeAssistantError(f'Invalid condition "{condition}" specified {config}')

    # Check for partials to properly determine if coroutine function
    check_factory = factory
    while isinstance(check_factory, ft.partial):
        check_factory = check_factory.func

    if asyncio.iscoroutinefunction(check_factory):
        return cast(
            ConditionCheckerType, await factory(hass, config, config_validation)
        )
    return cast(ConditionCheckerType, factory(config, config_validation))


async def async_and_from_config(
    hass: HomeAssistant, config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Create multi condition matcher using 'AND'."""
    if config_validation:
        config = cv.AND_CONDITION_SCHEMA(config)
    checks = [
        await async_from_config(hass, entry, False) for entry in config["conditions"]
    ]

    def if_and_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test and condition."""
        errors = []
        for check in checks:
            try:
                if not check(hass, variables):
                    return False
            except ConditionError as ex:
                errors.append(str(ex))
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(str(ex))

        # Raise the errors if no check was false
        if errors:
            raise ConditionError("Error in 'and' condition: " + ", ".join(errors))

        return True

    return if_and_condition


async def async_or_from_config(
    hass: HomeAssistant, config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Create multi condition matcher using 'OR'."""
    if config_validation:
        config = cv.OR_CONDITION_SCHEMA(config)
    checks = [
        await async_from_config(hass, entry, False) for entry in config["conditions"]
    ]

    def if_or_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test or condition."""
        errors = []
        for check in checks:
            try:
                if check(hass, variables):
                    return True
            except ConditionError as ex:
                errors.append(str(ex))
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(str(ex))

        # Raise the errors if no check was true
        if errors:
            raise ConditionError("Error in 'or' condition: " + ", ".join(errors))

        return False

    return if_or_condition


async def async_not_from_config(
    hass: HomeAssistant, config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Create multi condition matcher using 'NOT'."""
    if config_validation:
        config = cv.NOT_CONDITION_SCHEMA(config)
    checks = [
        await async_from_config(hass, entry, False) for entry in config["conditions"]
    ]

    def if_not_condition(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test not condition."""
        errors = []
        for check in checks:
            try:
                if check(hass, variables):
                    return False
            except ConditionError as ex:
                errors.append(str(ex))
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(str(ex))

        # Raise the errors if no check was true
        if errors:
            raise ConditionError("Error in 'not' condition: " + ", ".join(errors))

        return True

    return if_not_condition


def numeric_state(
    hass: HomeAssistant,
    entity: Union[None, str, State],
    below: Optional[Union[float, str]] = None,
    above: Optional[Union[float, str]] = None,
    value_template: Optional[Template] = None,
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
    entity: Union[None, str, State],
    below: Optional[Union[float, str]] = None,
    above: Optional[Union[float, str]] = None,
    value_template: Optional[Template] = None,
    variables: TemplateVarsType = None,
    attribute: Optional[str] = None,
) -> bool:
    """Test a numeric state condition."""
    if entity is None:
        raise ConditionError("No entity specified")

    if isinstance(entity, str):
        entity_id = entity
        entity = hass.states.get(entity)

        if entity is None:
            raise ConditionError(f"Unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        raise ConditionError(
            f"Attribute '{attribute}' (of entity {entity_id}) does not exist"
        )

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
            raise ConditionError(f"Template error: {ex}") from ex

    if value in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        raise ConditionError("State is not available")

    try:
        fvalue = float(value)
    except ValueError as ex:
        raise ConditionError(
            f"Entity {entity_id} state '{value}' cannot be processed as a number"
        ) from ex

    if below is not None:
        if isinstance(below, str):
            below_entity = hass.states.get(below)
            if not below_entity or below_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                raise ConditionError(f"The below entity {below} is not available")
            if fvalue >= float(below_entity.state):
                return False
        elif fvalue >= below:
            return False

    if above is not None:
        if isinstance(above, str):
            above_entity = hass.states.get(above)
            if not above_entity or above_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                raise ConditionError(f"The above entity {above} is not available")
            if fvalue <= float(above_entity.state):
                return False
        elif fvalue <= above:
            return False

    return True


def async_numeric_state_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.NUMERIC_STATE_CONDITION_SCHEMA(config)
    entity_ids = config.get(CONF_ENTITY_ID, [])
    attribute = config.get(CONF_ATTRIBUTE)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def if_numeric_state(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test numeric state condition."""
        if value_template is not None:
            value_template.hass = hass

        return all(
            async_numeric_state(
                hass, entity_id, below, above, value_template, variables, attribute
            )
            for entity_id in entity_ids
        )

    return if_numeric_state


def state(
    hass: HomeAssistant,
    entity: Union[None, str, State],
    req_state: Any,
    for_period: Optional[timedelta] = None,
    attribute: Optional[str] = None,
) -> bool:
    """Test if state matches requirements.

    Async friendly.
    """
    if entity is None:
        raise ConditionError("No entity specified")

    if isinstance(entity, str):
        entity_id = entity
        entity = hass.states.get(entity)

        if entity is None:
            raise ConditionError(f"Unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        raise ConditionError(
            f"Attribute '{attribute}' (of entity {entity_id}) does not exist"
        )

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
            state_entity = hass.states.get(req_state_value)
            if not state_entity:
                continue
            state_value = state_entity.state
        is_state = value == state_value
        if is_state:
            break

    if for_period is None or not is_state:
        return is_state

    return dt_util.utcnow() - for_period > entity.last_changed


def state_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.STATE_CONDITION_SCHEMA(config)
    entity_ids = config.get(CONF_ENTITY_ID, [])
    req_states: Union[str, List[str]] = config.get(CONF_STATE, [])
    for_period = config.get("for")
    attribute = config.get(CONF_ATTRIBUTE)

    if not isinstance(req_states, list):
        req_states = [req_states]

    def if_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        return all(
            state(hass, entity_id, req_states, for_period, attribute)
            for entity_id in entity_ids
        )

    return if_state


def sun(
    hass: HomeAssistant,
    before: Optional[str] = None,
    after: Optional[str] = None,
    before_offset: Optional[timedelta] = None,
    after_offset: Optional[timedelta] = None,
) -> bool:
    """Test if current time matches sun requirements."""
    utcnow = dt_util.utcnow()
    today = dt_util.as_local(utcnow).date()
    before_offset = before_offset or timedelta(0)
    after_offset = after_offset or timedelta(0)

    sunrise_today = get_astral_event_date(hass, SUN_EVENT_SUNRISE, today)
    sunset_today = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)

    sunrise = sunrise_today
    sunset = sunset_today
    if today > dt_util.as_local(
        cast(datetime, sunrise_today)
    ).date() and SUN_EVENT_SUNRISE in (before, after):
        tomorrow = dt_util.as_local(utcnow + timedelta(days=1)).date()
        sunrise_tomorrow = get_astral_event_date(hass, SUN_EVENT_SUNRISE, tomorrow)
        sunrise = sunrise_tomorrow

    if today > dt_util.as_local(
        cast(datetime, sunset_today)
    ).date() and SUN_EVENT_SUNSET in (before, after):
        tomorrow = dt_util.as_local(utcnow + timedelta(days=1)).date()
        sunset_tomorrow = get_astral_event_date(hass, SUN_EVENT_SUNSET, tomorrow)
        sunset = sunset_tomorrow

    if sunrise is None and SUN_EVENT_SUNRISE in (before, after):
        # There is no sunrise today
        return False

    if sunset is None and SUN_EVENT_SUNSET in (before, after):
        # There is no sunset today
        return False

    if before == SUN_EVENT_SUNRISE and utcnow > cast(datetime, sunrise) + before_offset:
        return False

    if before == SUN_EVENT_SUNSET and utcnow > cast(datetime, sunset) + before_offset:
        return False

    if after == SUN_EVENT_SUNRISE and utcnow < cast(datetime, sunrise) + after_offset:
        return False

    if after == SUN_EVENT_SUNSET and utcnow < cast(datetime, sunset) + after_offset:
        return False

    return True


def sun_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with sun based condition."""
    if config_validation:
        config = cv.SUN_CONDITION_SCHEMA(config)
    before = config.get("before")
    after = config.get("after")
    before_offset = config.get("before_offset")
    after_offset = config.get("after_offset")

    def time_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return sun(hass, before, after, before_offset, after_offset)

    return time_if


def template(
    hass: HomeAssistant, value_template: Template, variables: TemplateVarsType = None
) -> bool:
    """Test if template condition matches."""
    return run_callback_threadsafe(
        hass.loop, async_template, hass, value_template, variables
    ).result()


def async_template(
    hass: HomeAssistant, value_template: Template, variables: TemplateVarsType = None
) -> bool:
    """Test if template condition matches."""
    try:
        value: str = value_template.async_render(variables, parse_result=False)
    except TemplateError as ex:
        raise ConditionError(f"Error in 'template' condition: {ex}") from ex

    return value.lower() == "true"


def async_template_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.TEMPLATE_CONDITION_SCHEMA(config)
    value_template = cast(Template, config.get(CONF_VALUE_TEMPLATE))

    def template_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate template based if-condition."""
        value_template.hass = hass

        return async_template(hass, value_template, variables)

    return template_if


def time(
    hass: HomeAssistant,
    before: Optional[Union[dt_util.dt.time, str]] = None,
    after: Optional[Union[dt_util.dt.time, str]] = None,
    weekday: Union[None, str, Container[str]] = None,
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
        after = dt_util.dt.time(0)
    elif isinstance(after, str):
        after_entity = hass.states.get(after)
        if not after_entity:
            raise ConditionError(
                f"Error in 'time' condition: The 'after' entity {after} is not available"
            )
        after = dt_util.dt.time(
            after_entity.attributes.get("hour", 23),
            after_entity.attributes.get("minute", 59),
            after_entity.attributes.get("second", 59),
        )

    if before is None:
        before = dt_util.dt.time(23, 59, 59, 999999)
    elif isinstance(before, str):
        before_entity = hass.states.get(before)
        if not before_entity:
            raise ConditionError(
                f"Error in 'time' condition: The 'before' entity {before} is not available"
            )
        before = dt_util.dt.time(
            before_entity.attributes.get("hour", 23),
            before_entity.attributes.get("minute", 59),
            before_entity.attributes.get("second", 59),
            999999,
        )

    if after < before:
        if not after <= now_time < before:
            return False
    else:
        if before <= now_time < after:
            return False

    if weekday is not None:
        now_weekday = WEEKDAYS[now.weekday()]

        if (
            isinstance(weekday, str)
            and weekday != now_weekday
            or now_weekday not in weekday
        ):
            return False

    return True


def time_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with time based condition."""
    if config_validation:
        config = cv.TIME_CONDITION_SCHEMA(config)
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    def time_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return time(hass, before, after, weekday)

    return time_if


def zone(
    hass: HomeAssistant,
    zone_ent: Union[None, str, State],
    entity: Union[None, str, State],
) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
    if zone_ent is None:
        raise ConditionError("No zone specified")

    if isinstance(zone_ent, str):
        zone_ent_id = zone_ent
        zone_ent = hass.states.get(zone_ent)

        if zone_ent is None:
            raise ConditionError(f"Unknown zone {zone_ent_id}")

    if entity is None:
        raise ConditionError("No entity specified")

    if isinstance(entity, str):
        entity_id = entity
        entity = hass.states.get(entity)

        if entity is None:
            raise ConditionError(f"Unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None:
        raise ConditionError(f"Entity {entity_id} has no 'latitude' attribute")

    if longitude is None:
        raise ConditionError(f"Entity {entity_id} has no 'longitude' attribute")

    return zone_cmp.in_zone(
        zone_ent, latitude, longitude, entity.attributes.get(ATTR_GPS_ACCURACY, 0)
    )


def zone_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with zone based condition."""
    if config_validation:
        config = cv.ZONE_CONDITION_SCHEMA(config)
    entity_ids = config.get(CONF_ENTITY_ID, [])
    zone_entity_ids = config.get(CONF_ZONE, [])

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
                except ConditionError as ex:
                    errors.append(str(ex))

            if not entity_ok:
                all_ok = False

        # Raise the errors only if no definitive result was found
        if errors and not all_ok:
            raise ConditionError("Error in 'zone' condition: " + ", ".join(errors))

        return all_ok

    return if_in_zone


async def async_device_from_config(
    hass: HomeAssistant, config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Test a device condition."""
    if config_validation:
        config = cv.DEVICE_CONDITION_SCHEMA(config)
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], "condition"
    )
    return cast(
        ConditionCheckerType,
        platform.async_condition_from_config(config, config_validation),  # type: ignore
    )


async def async_validate_condition_config(
    hass: HomeAssistant, config: Union[ConfigType, Template]
) -> Union[ConfigType, Template]:
    """Validate config."""
    if isinstance(config, Template):
        return config

    condition = config[CONF_CONDITION]
    if condition in ("and", "not", "or"):
        conditions = []
        for sub_cond in config["conditions"]:
            sub_cond = await async_validate_condition_config(hass, sub_cond)
            conditions.append(sub_cond)
        config["conditions"] = conditions

    if condition == "device":
        config = cv.DEVICE_CONDITION_SCHEMA(config)
        assert not isinstance(config, Template)
        platform = await async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "condition"
        )
        return cast(ConfigType, platform.CONDITION_SCHEMA(config))  # type: ignore

    return config


@callback
def async_extract_entities(config: Union[ConfigType, Template]) -> Set[str]:
    """Extract entities from a condition."""
    referenced: Set[str] = set()
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
def async_extract_devices(config: Union[ConfigType, Template]) -> Set[str]:
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

        device_id = config.get(CONF_DEVICE_ID)

        if device_id is not None:
            referenced.add(device_id)

    return referenced
