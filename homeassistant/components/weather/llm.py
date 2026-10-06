"""LLM tools for the weather integration."""

from datetime import datetime, timedelta
from operator import attrgetter
from typing import cast, override

import probatio

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.intent import MatchFailedReason
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from . import SERVICE_GET_FORECASTS, Forecast, WeatherEntityFeature
from .const import DOMAIN

# Forecast cadence (daily/hourly/twice_daily) is an implementation detail the
# model must not guess: a wrong guess surfaces as a tool failure instead of
# being resolved deterministically. Home Assistant selects the best supported
# cadence for the requested period instead.
FORECAST_FEATURE_BY_TYPE = {
    "daily": WeatherEntityFeature.FORECAST_DAILY,
    "hourly": WeatherEntityFeature.FORECAST_HOURLY,
    "twice_daily": WeatherEntityFeature.FORECAST_TWICE_DAILY,
}
FORECAST_FEATURES = (
    WeatherEntityFeature.FORECAST_DAILY
    | WeatherEntityFeature.FORECAST_HOURLY
    | WeatherEntityFeature.FORECAST_TWICE_DAILY
)

# How long a single forecast entry of each cadence covers, used to determine
# whether it overlaps the requested window rather than requiring its start
# timestamp to fall inside that window (a daily entry starts at midnight, so
# it would otherwise be discarded for a same-day partial-day request). Only
# used as a fallback for the final entry in a forecast, since every other
# entry's end is derived from the following entry's start.
FORECAST_TYPE_DURATION = {
    "daily": timedelta(days=1),
    "hourly": timedelta(hours=1),
    "twice_daily": timedelta(hours=12),
}

# Periods that describe part of a day are best served by the most granular
# forecast available; whole-day and multi-day periods are best served by the
# coarsest. Each tuple is a fallback order, most preferred first, used when the
# entity doesn't support the top choice.
_PARTIAL_DAY_PERIODS = {"this_afternoon", "tonight", "next_24_hours"}
_PARTIAL_DAY_PREFERENCE = ("hourly", "twice_daily", "daily")
_WHOLE_DAY_PREFERENCE = ("daily", "twice_daily", "hourly")


def _select_forecast_type(period: str, supported_features: int) -> str | None:
    """Return the best supported forecast cadence for the requested period."""
    preference = (
        _PARTIAL_DAY_PREFERENCE
        if period in _PARTIAL_DAY_PERIODS
        else _WHOLE_DAY_PREFERENCE
    )
    for forecast_type in preference:
        if supported_features & FORECAST_FEATURE_BY_TYPE[forecast_type]:
            return forecast_type
    return None


class GetForecastTool(Tool):
    """LLM tool to retrieve weather forecasts."""

    name = "weather__get_forecast"
    title = "Get weather forecast for a time window"
    description = (
        "Get forecast data for an exposed weather entity within a requested time "
        "window. The returned entries can be summarized to answer the user. Map "
        "conversational dates like 'tomorrow' or 'this Thursday' to the matching "
        "period."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN

    def __init__(self, names: list[str]) -> None:
        """Initialize the forecast tool."""
        self.parameters = probatio.Schema(
            {
                probatio.Required("weather"): probatio.In(names),
                probatio.Required(
                    "period",
                    description=(
                        "Requested time window: today, tomorrow, this_afternoon, "
                        "tonight, next_24_hours, next_7_days, or a weekday name "
                        "(Monday through Sunday) for the next occurrence of that "
                        "weekday. Map conversational requests such as 'this "
                        "Thursday' to the weekday name, and 'this week' to "
                        "next_7_days. Use this_afternoon, tonight, or "
                        "next_24_hours for requests within a day."
                    ),
                ): probatio.In(
                    [
                        "today",
                        "tomorrow",
                        "this_afternoon",
                        "tonight",
                        "next_24_hours",
                        "next_7_days",
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                ),
            }
        )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Retrieve the requested forecast."""
        data = self.parameters(tool_input.tool_args)
        if not llm_context.assistant:
            return ToolResult(data={"error": "Weather entity not found"}, error=True)

        start, end = _get_forecast_window(data["period"])

        # Tool discovery only advertises aliases from forecast-capable
        # entities, so matching must be restricted the same way or a
        # same-named current-conditions-only entity could create a false
        # ambiguous match.
        forecast_capable_states = [
            state
            for state in hass.states.async_all(DOMAIN)
            if state.attributes.get("supported_features", 0) & FORECAST_FEATURES
        ]
        if not forecast_capable_states:
            # async_match_targets treats an empty states list as "no
            # override" and searches every entity in the domain instead, so
            # this case must be handled explicitly rather than passed through.
            return ToolResult(data={"error": "Weather entity not found"}, error=True)

        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["weather"],
                domains=[DOMAIN],
                assistant=llm_context.assistant,
            ),
            states=forecast_capable_states,
        )
        if not result.is_match:
            message = (
                "Weather entity name is ambiguous"
                if result.no_match_reason is MatchFailedReason.DUPLICATE_NAME
                else "Weather entity not found"
            )
            return ToolResult(data={"error": message}, error=True)

        weather_state = result.states[0]
        supported_features = weather_state.attributes.get("supported_features", 0)
        forecast_type = _select_forecast_type(data["period"], supported_features)
        if forecast_type is None:
            return ToolResult(
                data={
                    "error": (
                        "Weather entity does not support forecasts for the "
                        "requested period"
                    )
                },
                error=True,
            )

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECASTS,
            {
                "entity_id": weather_state.entity_id,
                "type": forecast_type,
            },
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )
        # Entity services omit unavailable entities from the response entirely,
        # so the entity_id may be missing even though it matched above.
        entity_response = cast(dict[str, dict[str, list[Forecast]]], response).get(
            weather_state.entity_id
        )
        if entity_response is None:
            return ToolResult(
                data={"error": "Weather entity is unavailable"}, error=True
            )
        forecast = entity_response["forecast"]
        duration = FORECAST_TYPE_DURATION[forecast_type]
        matching_forecast: list[Forecast] = []
        for index, entry in enumerate(forecast):
            entry_start = _forecast_datetime(entry["datetime"])
            # Prefer the next entry's own start as the end of this interval:
            # adding a fixed duration can land on the wrong local wall-clock
            # time across a DST change (e.g. a daily entry starting just
            # before the clocks change). Only the last entry, which has no
            # follow-up to derive an end from, falls back to the duration.
            if index + 1 < len(forecast):
                entry_end = _forecast_datetime(forecast[index + 1]["datetime"])
            else:
                # Apply the duration in local wall-clock time rather than to
                # the entry's (possibly fixed-offset) tzinfo directly: a
                # provider's fixed UTC offset doesn't account for a DST change
                # between the entry and its computed end, which would
                # otherwise over- or under-shoot the real calendar boundary.
                entry_end = dt_util.as_local(entry_start) + duration
            if entry_start < end and entry_end > start:
                # Normalize to an ISO string: some providers (e.g. IPMA) put a
                # native datetime object in this field, which isn't JSON-safe.
                matching_forecast.append({**entry, "datetime": entry_start.isoformat()})
        return ToolResult(
            data=cast(dict[str, JsonValueType], {"forecast": matching_forecast})
        )


def _forecast_datetime(value: datetime | str) -> datetime:
    """Parse a forecast datetime, treating timezone-naive values as local.

    Providers may supply either an ISO-formatted string or a native datetime
    object (for example IPMA's forecasts pass a datetime straight through).
    """
    parsed: datetime | None
    if isinstance(value, datetime):
        parsed = value
    elif (parsed := dt_util.parse_datetime(value)) is None:
        raise HomeAssistantError(f"Invalid forecast datetime: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


def _get_forecast_window(period: str) -> tuple[datetime, datetime]:
    """Return local datetimes delimiting a conversational forecast period."""
    now = dt_util.now()
    today = dt_util.start_of_local_day(now)
    if period == "today":
        start = today
        end = today + timedelta(days=1)
    elif period == "tomorrow":
        start = today + timedelta(days=1)
        end = start + timedelta(days=1)
    elif period == "this_afternoon":
        start = today.replace(hour=12)
        end = today.replace(hour=18)
    elif period == "tonight":
        start = today.replace(hour=18)
        end = (today + timedelta(days=1)).replace(hour=6)
    elif period == "next_24_hours":
        start = now
        end = dt_util.as_local(dt_util.as_utc(now) + timedelta(hours=24))
    elif period == "next_7_days":
        start = today
        end = today + timedelta(days=7)
    else:
        weekday = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ).index(period)
        start = today + timedelta(days=(weekday - today.weekday()) % 7)
        end = start + timedelta(days=1)

    return start, end


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the weather forecast tool when a forecast-capable entity is exposed."""
    if api_id != LLM_API_ASSIST or not llm_context.assistant:
        return None

    entity_registry = er.async_get(hass)
    names: set[str] = set()
    for state in sorted(hass.states.async_all(DOMAIN), key=attrgetter("name")):
        if not async_should_expose(hass, llm_context.assistant, state.entity_id):
            continue
        if not state.attributes.get("supported_features", 0) & FORECAST_FEATURES:
            continue
        entity_entry = entity_registry.async_get(state.entity_id)
        names.update(intent.async_get_entity_aliases(hass, entity_entry, state=state))

    if not names:
        return None
    return LLMTools(tools=[GetForecastTool(sorted(names))])
