"""Offer sun based automation rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckerType,
    ConditionConfig,
    condition_trace_set_result,
    condition_trace_update_result,
    trace_condition_function,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util import dt as dt_util

_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Optional("before"): cv.sun_event,
    vol.Optional("before_offset"): cv.time_period,
    vol.Optional("after"): vol.All(
        vol.Lower, vol.Any(SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE)
    ),
    vol.Optional("after_offset"): cv.time_period,
}

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            _OPTIONS_SCHEMA_DICT,
            cv.has_at_least_one_key("before", "after"),
        )
    }
)


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


class SunCondition(Condition):
    """Sun condition."""

    _options: dict[str, Any]

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        assert config.options is not None
        self._options = config.options

    async def async_get_checker(self) -> ConditionCheckerType:
        """Wrap action method with sun based condition."""
        before = self._options.get("before")
        after = self._options.get("after")
        before_offset = self._options.get("before_offset")
        after_offset = self._options.get("after_offset")

        @trace_condition_function
        def sun_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
            """Validate time based if-condition."""
            return sun(hass, before, after, before_offset, after_offset)

        return sun_if


CONDITIONS: dict[str, type[Condition]] = {
    "_": SunCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the sun conditions."""
    return CONDITIONS
