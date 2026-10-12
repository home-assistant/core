"""LLM tools for the history integration."""

import csv
from datetime import datetime, timedelta
import io
from typing import Any, Literal, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.components.recorder import get_instance, statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

type _Period = Literal["5minute", "hour", "day", "week", "month"]
type _StatisticType = Literal["change", "max", "mean", "min"]

_DEFAULT_TIME_SPAN = timedelta(days=1)
_MAX_ROWS = 500
# The shortest length of each period, used to estimate the number of rows.
_PERIOD_LENGTH: dict[_Period, timedelta] = {
    "5minute": timedelta(minutes=5),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=28),
}
# The longest time span each period is picked for by default.
_AUTO_PERIOD_MAX_SPAN: list[tuple[timedelta, _Period]] = [
    (timedelta(hours=6), "5minute"),
    (timedelta(days=2), "hour"),
    (timedelta(days=62), "day"),
    (timedelta(days=366), "week"),
]
_UNIT_MISMATCH = (
    "Statistics are recorded in {unit}, which cannot be converted to the unit "
    "of the entity."
)
_NO_STATISTICS = "No statistics are recorded for this entity."


def _auto_period(span: timedelta) -> _Period:
    """Return a statistics period that gives a compact result for the span."""
    for max_span, period in _AUTO_PERIOD_MAX_SPAN:
        if span <= max_span:
            return period
    return "month"


def _format_time(timestamp: float) -> str:
    """Format a timestamp as a local ISO 8601 datetime."""
    return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).isoformat(
        timespec="seconds"
    )


def _format_number(value: float | None) -> str:
    """Format a statistics value compactly."""
    return "" if value is None else str(round(value, 3))


def _to_csv(header: list[str], rows: list[list[str]]) -> str:
    """Return the rows as CSV."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def _get_statistics(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime,
    entity_ids: list[str],
    period: _Period,
) -> dict[str, Any]:
    """Fetch and format the long-term statistics in the recorder executor."""
    metadata = statistics.get_metadata(hass, statistic_ids=set(entity_ids))
    result: dict[str, Any] = {}
    for entity_id in entity_ids:
        if entity_id not in metadata:
            result[entity_id] = {"error": _NO_STATISTICS}
            continue
        meta = metadata[entity_id][1]
        types: list[_StatisticType] = []
        if meta["mean_type"] is StatisticMeanType.ARITHMETIC:
            types.extend(["mean", "min", "max"])
        elif meta["mean_type"] is StatisticMeanType.CIRCULAR:
            types.append("mean")
        if meta["has_sum"]:
            types.append("change")
        # Statistics are converted to the unit of the current state when possible.
        unit = statistics.get_display_unit(
            hass, entity_id, meta["unit_class"], meta["unit_of_measurement"]
        )
        if (state := hass.states.get(entity_id)) and state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        ) != unit:
            result[entity_id] = {"error": _UNIT_MISMATCH.format(unit=unit)}
            continue
        rows = statistics.statistics_during_period(
            hass, start_time, end_time, {entity_id}, period, None, set(types)
        ).get(entity_id, [])
        entry: dict[str, Any] = {}
        if unit:
            entry["unit"] = unit
        entry["csv"] = _to_csv(
            ["start", *types],
            [
                [
                    _format_time(row["start"]),
                    *(_format_number(row.get(stat_type)) for stat_type in types),
                ]
                for row in rows
            ],
        )
        result[entity_id] = entry
    return result


def _parse_time(value: str) -> datetime | None:
    """Parse a datetime string, assuming local time when no offset is given."""
    if (parsed := dt_util.parse_datetime(value)) is None:
        return None
    return dt_util.as_utc(parsed)


class GetHistoryTool(Tool):
    """LLM Tool allowing querying the long-term statistics of entities."""

    name = "history__get_history"
    title = "Get history"
    description = (
        "Retrieve the long-term statistics of one or more entities as CSV, with "
        "times as ISO 8601 datetimes in local time. Use this to answer questions "
        "about past values or how a value evolved over time. Each row aggregates "
        "one period, such as the mean, min and max of a temperature or the change "
        "of an energy meter. Statistics are only available for entities with "
        "numeric statistics (sensors with a state class) and only cover completed "
        "periods. Values are in the unit of the entity."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "entity_ids",
                description="Entity IDs to get the history for (e.g. 'sensor.outside_temperature').",
            ): probatio.All([cv.entity_id], probatio.Length(min=1)),
            probatio.Optional(
                "start_time",
                description=(
                    "Start of the time span as an ISO 8601 datetime. Local time is "
                    "used when no UTC offset is given (default: 24 hours before "
                    "end_time)."
                ),
            ): str,
            probatio.Optional(
                "end_time",
                description=(
                    "End of the time span as an ISO 8601 datetime. Local time is "
                    "used when no UTC offset is given (default: now)."
                ),
            ): str,
            probatio.Optional(
                "period",
                description=(
                    "The length of each row. 5minute rows are usually kept for "
                    "10 days (default: picked from the length of the time span)."
                ),
            ): probatio.In(list(_PERIOD_LENGTH)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Query the long-term statistics."""
        args = self.parameters(tool_input.tool_args)

        end_time = (
            _parse_time(args["end_time"]) if "end_time" in args else dt_util.utcnow()
        )
        if end_time is None:
            return ToolResult(data={"error": "Invalid end_time"}, error=True)

        start_time = (
            _parse_time(args["start_time"])
            if "start_time" in args
            else end_time - _DEFAULT_TIME_SPAN
        )
        if start_time is None:
            return ToolResult(data={"error": "Invalid start_time"}, error=True)

        if start_time >= end_time:
            return ToolResult(
                data={"error": "start_time must be before end_time"}, error=True
            )

        span = end_time - start_time
        period: _Period = args.get("period") or _auto_period(span)
        if span / _PERIOD_LENGTH[period] > _MAX_ROWS:
            return ToolResult(
                data={
                    "error": (
                        f"The time span has more than {_MAX_ROWS} {period} rows. "
                        "Use a longer period or a shorter time span."
                    )
                },
                error=True,
            )

        result: JsonObjectType = {
            "period": period,
            "entities": await get_instance(hass).async_add_executor_job(
                _get_statistics,
                hass,
                start_time,
                end_time,
                args["entity_ids"],
                period,
            ),
        }
        return ToolResult(data={"result": result})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the history LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[GetHistoryTool()])
