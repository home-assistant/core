"""LLM tools for the history integration."""

import csv
from datetime import datetime, timedelta
import io
from typing import Any, Literal, cast, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.components.recorder import get_instance, history, statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.helpers.significant_change import (
    PLATFORM as SIGNIFICANT_CHANGE_PLATFORM,
)
from homeassistant.loader import async_get_integrations
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

type _Period = Literal["5minute", "hour", "day", "week", "month"]
type _StatisticType = Literal["change", "max", "mean", "min"]

SOURCE_STATISTICS = "statistics"
SOURCE_STATE_CHANGES = "state_changes"

_DEFAULT_PERIOD = timedelta(days=1)
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 1000
_PERIODS: list[_Period] = ["5minute", "hour", "day", "week", "month"]
# The longest time span each statistics period is picked for by default.
_AUTO_PERIOD_MAX_SPAN: list[tuple[timedelta, _Period]] = [
    (timedelta(hours=6), "5minute"),
    (timedelta(days=2), "hour"),
    (timedelta(days=62), "day"),
    (timedelta(days=366), "week"),
]
_UNIT_MISMATCH = (
    "Statistics are recorded in {unit}, which cannot be converted to the unit "
    f"of the entity. Use source '{SOURCE_STATE_CHANGES}' instead."
)
# Media player attributes change during playback, which adds many rows.
_SKIP_SIGNIFICANT_ATTRIBUTES_DOMAINS = {"media_player"}
_NO_STATISTICS = f"No statistics recorded. Use source '{SOURCE_STATE_CHANGES}' instead."


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


def _limit_rows(entry: dict[str, Any], rows: list[Any], limit: int) -> list[Any]:
    """Keep the most recent rows and record the total when rows are dropped."""
    if len(rows) > limit:
        entry["total"] = len(rows)
    return rows[-limit:]


def _get_statistics(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime,
    entity_ids: list[str],
    period: _Period,
    limit: int,
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
                for row in _limit_rows(entry, rows, limit)
            ],
        )
        result[entity_id] = entry
    return result


def _format_value(value: Any) -> str:
    """Format an attribute value for a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json_dumps(value)
    return str(value)


def _get_state_changes(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime,
    entity_ids: list[str],
    significant_attributes: dict[str, set[str]],
    include_full_attributes: bool,
    limit: int,
) -> dict[str, Any]:
    """Fetch and format the state changes in the recorder executor."""
    states: dict[str, list[Any]] = {}
    # Attribute-only changes are needed for entities with significant attributes.
    for attribute_changes in (False, True):
        if query_ids := [
            entity_id
            for entity_id in entity_ids
            if (split_entity_id(entity_id)[0] in significant_attributes)
            is attribute_changes
        ]:
            states.update(
                history.get_significant_states(
                    hass,
                    start_time,
                    end_time,
                    query_ids,
                    significant_changes_only=not attribute_changes,
                    no_attributes=not (attribute_changes or include_full_attributes),
                )
            )
    result: dict[str, Any] = {}
    for entity_id in entity_ids:
        entry: dict[str, Any] = {}
        if (current := hass.states.get(entity_id)) and (
            unit := current.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        ):
            entry["unit"] = unit
        entity_states = cast(list[State], states.get(entity_id, []))
        columns = [
            attribute
            for attribute in sorted(
                significant_attributes.get(split_entity_id(entity_id)[0], ())
            )
            if any(
                state.attributes.get(attribute) is not None for state in entity_states
            )
        ]
        rows: list[list[str]] = []
        previous: list[str] | None = None
        for state in entity_states:
            values = [
                state.state,
                *(_format_value(state.attributes.get(column)) for column in columns),
            ]
            # Skip rows where only insignificant attributes changed.
            if values == previous:
                continue
            previous = values
            rows.append(
                [
                    _format_time(state.last_updated_timestamp),
                    *values,
                    *(
                        [json_dumps(state.attributes)]
                        if include_full_attributes
                        else []
                    ),
                ]
            )
        entry["csv"] = _to_csv(
            [
                "time",
                "state",
                *columns,
                *(["attributes"] if include_full_attributes else []),
            ],
            _limit_rows(entry, rows, limit),
        )
        result[entity_id] = entry
    return result


async def _async_get_significant_attributes(
    hass: HomeAssistant, entity_ids: list[str]
) -> dict[str, set[str]]:
    """Return the significant attributes declared by the entities' domains."""
    domains = {
        split_entity_id(entity_id)[0] for entity_id in entity_ids
    } - _SKIP_SIGNIFICANT_ATTRIBUTES_DOMAINS
    result: dict[str, set[str]] = {}
    for domain, integration in (await async_get_integrations(hass, domains)).items():
        if isinstance(integration, Exception) or not integration.platforms_exists(
            (SIGNIFICANT_CHANGE_PLATFORM,)
        ):
            continue
        platform = await integration.async_get_platform(SIGNIFICANT_CHANGE_PLATFORM)
        if attributes := getattr(platform, "SIGNIFICANT_ATTRIBUTES", None):
            result[domain] = set(attributes)
    return result


def _parse_time(value: str) -> datetime | None:
    """Parse a datetime string, assuming local time when no offset is given."""
    if (parsed := dt_util.parse_datetime(value)) is None:
        return None
    return dt_util.as_utc(parsed)


class GetHistoryTool(Tool):
    """LLM Tool allowing querying the recorded history of entities."""

    name = "history__get_history"
    title = "Get history"
    description = (
        "Retrieve the recorded history of one or more entities as CSV, with times "
        "as ISO 8601 datetimes in local time. Use this to answer questions about "
        "past values, when something changed, or how a value evolved over time. "
        f"Source '{SOURCE_STATISTICS}' (default) returns aggregated values per "
        "period, such as the mean, min and max of a temperature or the change of "
        "an energy meter. It is only available for entities with numeric "
        "statistics (sensors with a state class) and only covers completed "
        "periods. "
        f"Source '{SOURCE_STATE_CHANGES}' returns each recorded state change. Use "
        "it for entities without statistics, to find out when something changed, "
        "or when the exact values are needed. For some domains, such as climate "
        "and cover, it also returns the important attributes as "
        "columns, with a row for each change of them. The first row is the state "
        "at the start of the period. Raw state changes are usually kept for 10 "
        "days. "
        "If there are more rows than the limit, only the most recent rows are "
        "returned and 'total' shows how many rows there are."
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
                "source",
                description=(
                    f"'{SOURCE_STATISTICS}' for aggregated values or "
                    f"'{SOURCE_STATE_CHANGES}' for each recorded state change "
                    f"(default: '{SOURCE_STATISTICS}')."
                ),
                default=SOURCE_STATISTICS,
            ): probatio.In([SOURCE_STATISTICS, SOURCE_STATE_CHANGES]),
            probatio.Optional(
                "start_time",
                description=(
                    "Start of the period as an ISO 8601 datetime. Local time is "
                    "used when no UTC offset is given (default: 24 hours before "
                    "end_time)."
                ),
            ): str,
            probatio.Optional(
                "end_time",
                description=(
                    "End of the period as an ISO 8601 datetime. Local time is "
                    "used when no UTC offset is given (default: now)."
                ),
            ): str,
            probatio.Optional(
                "period",
                description=(
                    f"Only for source '{SOURCE_STATISTICS}': the length of each "
                    "aggregated row. 5minute rows are usually kept for 10 days "
                    "(default: picked from the length of the requested time span)."
                ),
            ): probatio.In(_PERIODS),
            probatio.Optional(
                "include_full_attributes",
                description=(
                    f"Only for source '{SOURCE_STATE_CHANGES}': whether to include "
                    "all state attributes as JSON, for example the media details "
                    "of a media player (default: false)."
                ),
                default=False,
            ): probatio.All(probatio.Boolean(), bool),
            probatio.Optional(
                "limit",
                description=f"Maximum number of rows to return per entity (default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT}).",
                default=_DEFAULT_LIMIT,
            ): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=_MAX_LIMIT)
            ),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Query the recorded history."""
        args = self.parameters(tool_input.tool_args)

        end_time = (
            _parse_time(args["end_time"]) if "end_time" in args else dt_util.utcnow()
        )
        if end_time is None:
            return ToolResult(data={"error": "Invalid end_time"}, error=True)

        start_time = (
            _parse_time(args["start_time"])
            if "start_time" in args
            else end_time - _DEFAULT_PERIOD
        )
        if start_time is None:
            return ToolResult(data={"error": "Invalid start_time"}, error=True)

        if start_time >= end_time:
            return ToolResult(
                data={"error": "start_time must be before end_time"}, error=True
            )

        result: JsonObjectType = {
            "source": args["source"],
        }
        if args["source"] == SOURCE_STATISTICS:
            period = args.get("period") or _auto_period(end_time - start_time)
            result["period"] = period
            result["entities"] = await get_instance(hass).async_add_executor_job(
                _get_statistics,
                hass,
                start_time,
                end_time,
                args["entity_ids"],
                period,
                args["limit"],
            )
        else:
            result["entities"] = await get_instance(hass).async_add_executor_job(
                _get_state_changes,
                hass,
                start_time,
                end_time,
                args["entity_ids"],
                await _async_get_significant_attributes(hass, args["entity_ids"]),
                args["include_full_attributes"],
                args["limit"],
            )
        return ToolResult(data={"result": result})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the history LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[GetHistoryTool()])
