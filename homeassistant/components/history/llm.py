"""LLM tools for the history integration."""

import csv
from datetime import datetime, timedelta
import io
from typing import Any, Literal, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.components.recorder import get_instance, statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import HomeAssistant, callback, valid_entity_id
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
    rank_name_match,
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
_NO_STATISTICS = "No statistics are recorded for this ID."
_SEARCH_LIMIT = 20
_UNIT_CLASSES = sorted(
    unit_class for unit_class in statistics.UNIT_CLASS_TO_UNIT_CONVERTER if unit_class
)


def _auto_period(span: timedelta, short_term_available: bool) -> _Period:
    """Return a statistics period that gives a compact result for the span."""
    for max_span, period in _AUTO_PERIOD_MAX_SPAN:
        if span <= max_span and (period != "5minute" or short_term_available):
            return period
    return "month"


def _format_time(timestamp: float) -> str:
    """Format a timestamp as a local ISO 8601 datetime."""
    return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).isoformat(
        timespec="seconds"
    )


def _format_number(value: float | None) -> str:
    """Format a statistics value compactly."""
    return "" if value is None else f"{value:.6g}"


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
    statistic_ids: list[str],
    period: _Period,
    fall_back_to_hour: bool,
) -> JsonObjectType:
    """Fetch and format the long-term statistics in the recorder executor."""
    metadata = statistics.get_metadata(hass, statistic_ids=set(statistic_ids))
    statistic_types: dict[str, list[_StatisticType]] = {}
    for statistic_id, (_, meta) in metadata.items():
        types = statistic_types[statistic_id] = []
        if meta["mean_type"] is StatisticMeanType.ARITHMETIC:
            types.extend(["mean", "min", "max"])
        elif meta["mean_type"] is StatisticMeanType.CIRCULAR:
            types.append("mean")
        if meta["has_sum"]:
            types.append("change")

    def query(
        query_period: _Period, ids: set[str]
    ) -> dict[str, list[statistics.StatisticsRow]]:
        return statistics.statistics_during_period(
            hass,
            start_time,
            # The recorder moves the end time to the next period boundary, which
            # includes the period that starts at end_time.
            end_time - timedelta(microseconds=1),
            ids,
            query_period,
            None,
            {stat_type for types in statistic_types.values() for stat_type in types},
        )

    rows: dict[str, list[statistics.StatisticsRow]] = {}
    hourly_ids: set[str] = set()
    if statistic_types:
        rows = query(period, set(statistic_types))
        # Some statistics, such as imported ones, only have hourly rows.
        if fall_back_to_hour and (
            missing := {
                statistic_id
                for statistic_id in statistic_types
                if not rows.get(statistic_id)
            }
        ):
            hourly_rows = query("hour", missing)
            hourly_ids = {
                statistic_id
                for statistic_id, statistic_rows in hourly_rows.items()
                if statistic_rows
            }
            rows.update(
                {statistic_id: hourly_rows[statistic_id] for statistic_id in hourly_ids}
            )
    result: dict[str, Any] = {}
    for statistic_id in statistic_ids:
        if (columns := statistic_types.get(statistic_id)) is None:
            result[statistic_id] = {"error": _NO_STATISTICS}
            continue
        meta = metadata[statistic_id][1]
        # Statistics are converted to the unit of the current state when possible.
        unit = statistics.get_display_unit(
            hass, statistic_id, meta["unit_class"], meta["unit_of_measurement"]
        )
        entry: dict[str, Any] = {}
        if unit:
            entry["unit"] = unit
        if statistic_id in hourly_ids:
            entry["period"] = "hour"
        entry["csv"] = _to_csv(
            ["start", *columns],
            [
                [
                    _format_time(row["start"]),
                    *(_format_number(row.get(column)) for column in columns),
                ]
                for row in rows.get(statistic_id, [])
            ],
        )
        result[statistic_id] = entry
    return {"period": period, "statistics": result}


def _statistic_id(value: Any) -> str:
    """Validate an entity ID or the ID of a statistic without an entity."""
    if isinstance(value, str) and (
        valid_entity_id(value) or statistics.valid_statistic_id(value)
    ):
        return value
    raise probatio.Invalid(f"Invalid statistic ID: {value}")


def _parse_time(value: str) -> datetime | None:
    """Parse a datetime string, assuming local time when no offset is given."""
    try:
        parsed = dt_util.parse_datetime(value, raise_on_error=True)
    except ValueError:
        return None
    return dt_util.as_utc(parsed)


class GetHistoryTool(Tool):
    """LLM Tool allowing querying the long-term statistics."""

    name = "history__get_history"
    title = "Get history"
    description = (
        "Retrieve the long-term statistics of one or more entities or other "
        "statistics as CSV, with times as ISO 8601 datetimes in local time. Use this "
        "to answer questions about past values or how a value evolved over time. "
        "Each row aggregates one period, such as the mean, min and max of a temperature "
        "or the change of an energy meter. Entities only have statistics when they "
        "are numeric sensors with a state class, and integrations can add statistics "
        "without an entity. history__search_statistics finds them. Statistics are "
        "based on completed recording intervals, but daily, weekly, and monthly "
        "aggregates may be partial. Values are converted to the unit of the entity "
        "when possible. 'unit' gives the unit of the values. A 'period' on a "
        "statistic replaces the period of the result for that statistic."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "statistic_ids",
                description=(
                    "Entity IDs, like 'sensor.outside_temperature', or the IDs of "
                    "statistics without an entity, like 'opower:electricity'. "
                    "history__search_statistics finds them."
                ),
            ): probatio.All([probatio.All(str, _statistic_id)], probatio.Length(min=1)),
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
        auto_period = "period" not in args
        period: _Period = args.get("period") or _auto_period(
            span,
            # The recorder purges short-term statistics after keep_days.
            start_time
            >= dt_util.utcnow() - timedelta(days=get_instance(hass).keep_days),
        )
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

        result = await get_instance(hass).async_add_executor_job(
            _get_statistics,
            hass,
            start_time,
            end_time,
            args["statistic_ids"],
            period,
            auto_period and period == "5minute",
        )
        return ToolResult(data={"result": result})


class SearchStatisticsTool(Tool):
    """LLM Tool to search the long-term statistics."""

    name = "history__search_statistics"
    title = "Search statistics"
    description = (
        "Search the long-term statistics, also those without an entity, like the "
        "meters of a utility. A statistic with has_sum is a meter that counts up, "
        "like the energy used. A statistic with has_mean is a measurement, like a "
        "power or a temperature. Use the statistic_id with history__get_history "
        "or in the energy preferences. Returns at most "
        f"{_SEARCH_LIMIT} statistics per call."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "query",
                description=(
                    "Text to find in the statistic name or ID, case-insensitive."
                ),
            ): probatio.All(str, probatio.Strip, probatio.NonEmpty()),
            probatio.Optional(
                "unit_class",
                description=(
                    "The kind of unit. The energy dashboard uses energy and volume "
                    "for meters, and power and volume_flow_rate for rates."
                ),
            ): probatio.In(_UNIT_CLASSES),
            probatio.Optional(
                "statistic_type",
                description="sum for meters, mean for measurements.",
            ): probatio.In(["sum", "mean"]),
            probatio.Optional(
                "offset",
                description=(
                    "Number of results to skip. Use the next_offset of the "
                    "previous result."
                ),
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search the long-term statistics."""
        args = self.parameters(tool_input.tool_args)
        query: str | None = args["query"].casefold() if "query" in args else None
        unit_class: str | None = args.get("unit_class")
        offset: int = args["offset"]

        matches: list[tuple[int, str, str, JsonObjectType]] = []
        for item in await statistics.async_list_statistic_ids(
            hass, statistic_type=args.get("statistic_type")
        ):
            if unit_class is not None and item["unit_class"] != unit_class:
                continue
            statistic_id: str = item["statistic_id"]
            # Statistics of entities have no name of their own
            name: str | None = item["name"] or (
                state.name if (state := hass.states.get(statistic_id)) else None
            )
            rank = (
                0
                if query is None
                else rank_name_match(
                    query, (name,) if name else (), (), (statistic_id,)
                )
            )
            if rank is None:
                continue
            matches.append(
                (
                    rank,
                    (name or statistic_id).casefold(),
                    statistic_id,
                    {
                        "statistic_id": statistic_id,
                        "name": name,
                        "source": item["source"],
                        "unit": item["display_unit_of_measurement"],
                        "unit_class": item["unit_class"],
                        "has_sum": item["has_sum"],
                        "has_mean": item["mean_type"] is not StatisticMeanType.NONE,
                    },
                )
            )
        # Best matches first, like search__search
        matches.sort(key=lambda match: match[:3])

        result: JsonObjectType = {
            "statistics": [
                match[3] for match in matches[offset : offset + _SEARCH_LIMIT]
            ],
            "total": len(matches),
        }
        if (next_offset := offset + _SEARCH_LIMIT) < len(matches):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the history LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[GetHistoryTool(), SearchStatisticsTool()])
