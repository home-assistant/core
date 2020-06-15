"""Offer reusable conditions."""
import asyncio
from collections import deque
from datetime import datetime, timedelta
import functools as ft
import logging
import sys
from typing import Callable, Container, Optional, Set, Union, cast

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
from homeassistant.exceptions import HomeAssistantError, TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.async_ import run_callback_threadsafe
import homeassistant.util.dt as dt_util

FROM_CONFIG_FORMAT = "{}_from_config"
ASYNC_FROM_CONFIG_FORMAT = "async_{}_from_config"

_LOGGER = logging.getLogger(__name__)

ConditionCheckerType = Callable[[HomeAssistant, TemplateVarsType], bool]


async def async_from_config(
    hass: HomeAssistant, config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Turn a condition configuration into a method.

    Should be run on the event loop.
    """
    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(
            sys.modules[__name__], fmt.format(config.get(CONF_CONDITION)), None
        )

        if factory:
            break

    if factory is None:
        raise HomeAssistantError(
            'Invalid condition "{}" specified {}'.format(
                config.get(CONF_CONDITION), config
            )
        )

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
        try:
            for check in checks:
                if not check(hass, variables):
                    return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Error during and-condition: %s", ex)
            return False

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
        """Test and condition."""
        try:
            for check in checks:
                if check(hass, variables):
                    return True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Error during or-condition: %s", ex)

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
        try:
            for check in checks:
                if check(hass, variables):
                    return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Error during not-condition: %s", ex)

        return True

    return if_not_condition


def numeric_state(
    hass: HomeAssistant,
    entity: Union[None, str, State],
    below: Optional[float] = None,
    above: Optional[float] = None,
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
    below: Optional[float] = None,
    above: Optional[float] = None,
    value_template: Optional[Template] = None,
    variables: TemplateVarsType = None,
) -> bool:
    """Test a numeric state condition."""
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    if value_template is None:
        value = entity.state
    else:
        variables = dict(variables or {})
        variables["state"] = entity
        try:
            value = value_template.async_render(variables)
        except TemplateError as ex:
            _LOGGER.error("Template error: %s", ex)
            return False

    if value in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False

    try:
        fvalue = float(value)
    except ValueError:
        _LOGGER.warning(
            "Value cannot be processed as a number: %s (Offending entity: %s)",
            entity,
            value,
        )
        return False

    if below is not None and fvalue >= below:
        return False

    if above is not None and fvalue <= above:
        return False

    return True


def async_numeric_state_from_config(
    config: ConfigType, config_validation: bool = True
) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.NUMERIC_STATE_CONDITION_SCHEMA(config)
    entity_ids = config.get(CONF_ENTITY_ID, [])
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
                hass, entity_id, below, above, value_template, variables
            )
            for entity_id in entity_ids
        )

    return if_numeric_state


def state(
    hass: HomeAssistant,
    entity: Union[None, str, State],
    req_state: str,
    for_period: Optional[timedelta] = None,
) -> bool:
    """Test if state matches requirements.

    Async friendly.
    """
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False
    assert isinstance(entity, State)

    is_state = entity.state == req_state

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
    req_state = cast(str, config.get(CONF_STATE))
    for_period = config.get("for")

    def if_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        return all(
            state(hass, entity_id, req_state, for_period) for entity_id in entity_ids
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
        value = value_template.async_render(variables)
    except TemplateError as ex:
        _LOGGER.error("Error during template condition: %s", ex)
        return False

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
    before: Optional[dt_util.dt.time] = None,
    after: Optional[dt_util.dt.time] = None,
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
    if before is None:
        before = dt_util.dt.time(23, 59, 59, 999999)

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
        return time(before, after, weekday)

    return time_if


def zone(
    hass: HomeAssistant,
    zone_ent: Union[None, str, State],
    entity: Union[None, str, State],
) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
    if isinstance(zone_ent, str):
        zone_ent = hass.states.get(zone_ent)

    if zone_ent is None:
        return False

    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None or longitude is None:
        return False

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
    zone_entity_id = config.get(CONF_ZONE)

    def if_in_zone(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        return all(zone(hass, zone_entity_id, entity_id) for entity_id in entity_ids)

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

    if condition == "device":
        config = cv.DEVICE_CONDITION_SCHEMA(config)
        platform = await async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "condition"
        )
        return cast(ConfigType, platform.CONDITION_SCHEMA(config))  # type: ignore

    return config


@callback
def async_extract_entities(config: ConfigType) -> Set[str]:
    """Extract entities from a condition."""
    referenced: Set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
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
def async_extract_devices(config: ConfigType) -> Set[str]:
    """Extract devices from a condition."""
    referenced = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
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
