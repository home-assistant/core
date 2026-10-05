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


class GetForecastTool(Tool):
    """LLM tool to retrieve weather forecasts."""

    name = "weather__get_forecast"
    title = "Get weather forecast for a time window"
    description = (
        "Get forecast data for an exposed weather entity within a requested time "
        "window. Use hourly or twice_daily forecasts for part of a day and daily "
        "forecasts for whole days. The returned entries can be summarized to answer "
        "the user. Map conversational dates like 'tomorrow' or 'this Thursday' to "
        "the matching period."
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
                probatio.Required("forecast_type"): probatio.In(
                    ["daily", "hourly", "twice_daily"]
                ),
                probatio.Required(
                    "period",
                    description=(
                        "Requested time window: today, tomorrow, this_afternoon, "
                        "tonight, next_24_hours, this_week, or a weekday name "
                        "(Monday through Sunday) for the next occurrence of that "
                        "weekday. Map conversational requests such as 'this "
                        "Thursday' to the weekday name. Use this_afternoon, tonight, "
                        "or next_24_hours for requests within a day."
                    ),
                ): probatio.In(
                    [
                        "today",
                        "tomorrow",
                        "this_afternoon",
                        "tonight",
                        "next_24_hours",
                        "this_week",
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
            raise HomeAssistantError("Weather entity not found")

        start, end = _get_forecast_window(data["period"])

        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["weather"],
                domains=[DOMAIN],
                assistant=llm_context.assistant,
            ),
        )
        if not result.is_match:
            message = (
                "Weather entity name is ambiguous"
                if result.no_match_reason is MatchFailedReason.DUPLICATE_NAME
                else "Weather entity not found"
            )
            raise HomeAssistantError(message)

        weather_state = result.states[0]
        forecast_type = data["forecast_type"]
        supported_feature = {
            "daily": WeatherEntityFeature.FORECAST_DAILY,
            "hourly": WeatherEntityFeature.FORECAST_HOURLY,
            "twice_daily": WeatherEntityFeature.FORECAST_TWICE_DAILY,
        }[forecast_type]
        if (
            not weather_state.attributes.get("supported_features", 0)
            & supported_feature
        ):
            raise HomeAssistantError(
                f"Weather entity does not support {forecast_type} forecasts"
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
        forecast = cast(dict[str, dict[str, list[Forecast]]], response)[
            weather_state.entity_id
        ]["forecast"]
        matching_forecast = [
            entry
            for entry in forecast
            if start <= _forecast_datetime(entry["datetime"]) < end
        ]
        return ToolResult(
            data=cast(dict[str, JsonValueType], {"forecast": matching_forecast})
        )


def _forecast_datetime(value: str) -> datetime:
    """Parse a forecast datetime, treating timezone-naive values as local."""
    if (parsed := dt_util.parse_datetime(value)) is None:
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
        end = today + timedelta(days=1)
    elif period == "next_24_hours":
        start = now
        end = dt_util.as_local(dt_util.as_utc(now) + timedelta(hours=24))
    elif period == "this_week":
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
        if not state.attributes.get("supported_features", 0) & (
            WeatherEntityFeature.FORECAST_DAILY
            | WeatherEntityFeature.FORECAST_HOURLY
            | WeatherEntityFeature.FORECAST_TWICE_DAILY
        ):
            continue
        entity_entry = entity_registry.async_get(state.entity_id)
        names.update(intent.async_get_entity_aliases(hass, entity_entry, state=state))

    if not names:
        return None
    return LLMTools(tools=[GetForecastTool(sorted(names))])
