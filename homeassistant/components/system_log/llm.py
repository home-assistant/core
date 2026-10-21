"""LLM tools for the system_log integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
from typing import Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.const import KEY_DATA_LOGGING
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.hassio import is_hassio
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

from . import LogErrorHandler
from .const import DOMAIN
from .stream import _read_log_tail

_LOG_LEVELS = ["error", "warning", "critical"]
_DEFAULT_LIMIT = 25
_MAX_LIMIT = 50

# Newest lines read from each source, the time window can only cover these
LOG_QUERY_READ_LINES = 2000
_LOG_QUERY_DEFAULT_SPAN = timedelta(minutes=15)
_LOG_QUERY_DEFAULT_LIMIT = 100
_LOG_QUERY_MAX_LIMIT = 500
_LOG_QUERY_LEVELS = ["debug", "info", "warning", "error", "critical"]

# Records without a UTC offset are matched too, so they can be skipped
_RECORD_START = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}(?:[+-]\d{2}:\d{2})?) "
)
_RECORD_LEVEL = re.compile(r"(DEBUG|INFO|WARNING|ERROR|CRITICAL) ")


def _filter_log_entries(
    log_entries: list[dict[str, Any]],
    level: str | None = None,
    logger: str | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Filter and limit raw log entries."""
    predicates: list[Callable[[dict[str, Any]], bool]] = []

    if level:
        predicates.append(lambda entry: entry["level"].lower() == level)

    if logger and (logger_lower := logger.strip().lower()):
        predicates.append(
            lambda entry: (
                logger_lower in entry["name"].lower()
                or logger_lower in str(entry["source"][0]).lower()
            )
        )

    if predicates:
        log_entries = [
            entry
            for entry in log_entries
            if all(predicate(entry) for predicate in predicates)
        ]

    return log_entries[:limit]


def _format_entry(entry: dict[str, Any], include_traceback: bool) -> JsonObjectType:
    """Format a single raw log entry for LLM consumption."""
    source = entry["source"]
    entry_dict: JsonObjectType = {
        "name": entry["name"],
        "message": list(entry["message"]),
        "level": entry["level"],
        "source": list(source) if isinstance(source, (tuple, list)) else source,
        "count": entry["count"],
        "timestamp": dt_util.utc_from_timestamp(entry["timestamp"]).isoformat(),
        "first_occurred": dt_util.utc_from_timestamp(
            entry["first_occurred"]
        ).isoformat(),
    }
    if include_traceback and (exception := entry.get("exception")):
        entry_dict["exception"] = exception
    return entry_dict


class SystemLogGetEntriesTool(Tool):
    """LLM Tool allowing querying the system log."""

    name = "system_log__get_entries"
    title = "Get system log entries"
    description = (
        "Retrieve recent system log errors and warnings from Home Assistant. "
        "This inspects the in-memory system log, which only records WARNING, ERROR, "
        "and CRITICAL events (not DEBUG or INFO). Can filter by log level, integration "
        "or logger name, and choose whether to include full exception tracebacks."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "level",
                description="Filter by log level. Allowed values: 'error', 'warning', 'critical'.",
            ): probatio.All(str, probatio.Lower, probatio.In(_LOG_LEVELS)),
            probatio.Optional(
                "logger",
                description=(
                    "Filter by integration domain or logger name (case-insensitive "
                    "substring match, e.g. 'zwave_js', 'hue', 'automation')."
                ),
            ): str,
            probatio.Optional(
                "limit",
                description=f"Maximum number of log entries to return (default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT}).",
                default=_DEFAULT_LIMIT,
            ): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=_MAX_LIMIT)
            ),
            probatio.Optional(
                "include_traceback",
                description=(
                    "Whether to include full Python exception stack traces in the "
                    "returned entries (default: false)."
                ),
                default=False,
            ): probatio.All(probatio.Boolean(), bool),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Query the system log."""
        handler: LogErrorHandler | None = hass.data.get(DOMAIN)
        if handler is None:
            return ToolResult(
                data={"error": "System log integration is not loaded."}, error=True
            )

        args = self.parameters(tool_input.tool_args)
        filtered_entries = _filter_log_entries(
            handler.records.to_list(),
            level=args.get("level"),
            logger=args.get("logger"),
            limit=args["limit"],
        )
        include_traceback: bool = args["include_traceback"]
        return ToolResult(
            data={
                "result": [
                    _format_entry(entry, include_traceback)
                    for entry in filtered_entries
                ]
            }
        )


@dataclass(slots=True)
class _LogRecord:
    """A log record with the lines that continue it, like a traceback."""

    time: datetime
    message: str
    level: int | None


def _parse_log_records(lines: list[str]) -> list[_LogRecord]:
    """Parse log lines into records, oldest first.

    Records without a UTC offset are skipped, as they cannot be sorted
    against other sources.
    """
    records: list[_LogRecord] = []
    record: _LogRecord | None = None
    for line in lines:
        if match := _RECORD_START.match(line):
            time = datetime.fromisoformat(match[1])
            if time.tzinfo is None:
                record = None
                continue
            message = line[match.end() :]
            level = (
                logging.getLevelNamesMapping()[level_match[1]]
                if (level_match := _RECORD_LEVEL.match(message))
                else None
            )
            record = _LogRecord(time, message, level)
            records.append(record)
        elif record is not None:
            record.message += f"\n{line}"
    return records


def _parse_time(value: str) -> datetime | None:
    """Parse a datetime string, assuming local time when no offset is given."""
    try:
        parsed = dt_util.parse_datetime(value, raise_on_error=True)
    except ValueError:
        return None
    return dt_util.as_utc(parsed)


def _fair_limits(counts: dict[str, int], limit: int) -> dict[str, int]:
    """Split the limit over the sources, giving unused shares to the others."""
    limits: dict[str, int] = {}
    remaining = limit
    for index, (source, count) in enumerate(
        sorted(counts.items(), key=lambda item: item[1])
    ):
        limits[source] = min(count, remaining // (len(counts) - index))
        remaining -= limits[source]
    return limits


class SystemLogGetLogsTool(Tool):
    """LLM Tool querying the logs of one or more sources."""

    name = "system_log__get_logs"
    title = "Get logs"
    description = (
        "Read the full logs in a time window, merged into one timeline. This "
        "includes INFO and DEBUG records. Use system_log__get_entries first for "
        "a summary of Home Assistant errors and warnings. Use this tool to see "
        "what happened around a specific time, or to find the cause of an error. "
        "Records are sorted oldest first, with times in local time. If "
        "'not_read_before' is set for a source, records older than that time "
        "were not read."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN

    def __init__(self, sources: dict[str, str], default_sources: list[str]) -> None:
        """Initialize the tool with the descriptions of the sources by name."""
        self._default_sources = default_sources
        self.parameters = probatio.Schema(
            {
                probatio.Optional(
                    "source",
                    description=(
                        "Logs to read (default: "
                        f"{', '.join(self._default_sources)}). Available: "
                        + ", ".join(
                            f"{name} ({description})"
                            for name, description in sources.items()
                        )
                    ),
                ): probatio.All([probatio.In(list(sources))], probatio.Length(min=1)),
                probatio.Optional(
                    "start_time",
                    description=(
                        "Start of the time window as an ISO 8601 datetime. Local "
                        "time is used when no UTC offset is given (default: 15 "
                        "minutes before end_time)."
                    ),
                ): str,
                probatio.Optional(
                    "end_time",
                    description=(
                        "End of the time window as an ISO 8601 datetime. Local "
                        "time is used when no UTC offset is given (default: now)."
                    ),
                ): str,
                probatio.Optional(
                    "level",
                    description=(
                        "Minimum log level. Records without a level are always "
                        "included."
                    ),
                ): probatio.All(str, probatio.Lower, probatio.In(_LOG_QUERY_LEVELS)),
                probatio.Optional(
                    "contains",
                    description=(
                        "Only return records that contain this text (case-"
                        "insensitive). Matches the logger name and the message, "
                        "including tracebacks."
                    ),
                ): str,
                probatio.Optional(
                    "limit",
                    description=(
                        "Maximum number of records to return, split fairly over "
                        f"the sources (default: {_LOG_QUERY_DEFAULT_LIMIT}, "
                        f"max: {_LOG_QUERY_MAX_LIMIT})."
                    ),
                    default=_LOG_QUERY_DEFAULT_LIMIT,
                ): probatio.All(
                    probatio.Coerce(int),
                    probatio.Range(min=1, max=_LOG_QUERY_MAX_LIMIT),
                ),
            }
        )

    async def async_read_source(
        self, hass: HomeAssistant, source: str, lines: int
    ) -> list[str]:
        """Return the newest lines of the log of a source.

        Raise HomeAssistantError when the log cannot be read.
        """
        return await hass.async_add_executor_job(
            _read_log_tail, hass.data[KEY_DATA_LOGGING], lines
        )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Query the logs."""
        args = self.parameters(tool_input.tool_args)

        end_time = (
            _parse_time(args["end_time"]) if "end_time" in args else dt_util.utcnow()
        )
        if end_time is None:
            return ToolResult(data={"error": "Invalid end_time"}, error=True)
        start_time = (
            _parse_time(args["start_time"])
            if "start_time" in args
            else end_time - _LOG_QUERY_DEFAULT_SPAN
        )
        if start_time is None:
            return ToolResult(data={"error": "Invalid start_time"}, error=True)
        if start_time >= end_time:
            return ToolResult(
                data={"error": "start_time must be before end_time"}, error=True
            )

        min_level = (
            logging.getLevelNamesMapping()[args["level"].upper()]
            if "level" in args
            else None
        )
        contains = args.get("contains", "").lower()

        names: list[str] = args.get("source", self._default_sources)
        results = await asyncio.gather(
            *(
                self.async_read_source(hass, name, LOG_QUERY_READ_LINES)
                for name in names
            ),
            return_exceptions=True,
        )

        summary: dict[str, JsonObjectType] = {}
        matches: dict[str, list[_LogRecord]] = {}
        for name, result in zip(names, results, strict=True):
            if isinstance(result, HomeAssistantError):
                summary[name] = {"error": str(result)}
                continue
            if isinstance(result, BaseException):
                raise result
            records = _parse_log_records(result)
            matches[name] = [
                record
                for record in records
                if start_time <= record.time <= end_time
                and (
                    min_level is None
                    or record.level is None
                    or record.level >= min_level
                )
                and contains in record.message.lower()
            ]
            summary[name] = {"matched": len(matches[name])}
            if (
                len(result) >= LOG_QUERY_READ_LINES
                and records
                and records[0].time > start_time
            ):
                summary[name]["not_read_before"] = dt_util.as_local(
                    records[0].time
                ).isoformat(timespec="milliseconds")

        returned: list[tuple[str, _LogRecord]] = []
        for name, limit in _fair_limits(
            {name: len(records) for name, records in matches.items()},
            args["limit"],
        ).items():
            summary[name]["returned"] = limit
            if limit:
                returned.extend((name, record) for record in matches[name][-limit:])
        returned.sort(key=lambda item: item[1].time)

        return ToolResult(
            data={
                "records": [
                    {
                        "time": dt_util.as_local(record.time).isoformat(
                            timespec="milliseconds"
                        ),
                        "source": name,
                        "message": record.message,
                    }
                    for name, record in returned
                ],
                "sources": dict(summary.items()),
            }
        )


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the system log LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    tools: list[Tool] = [SystemLogGetEntriesTool()]
    # The Supervisor integration provides the logs on Supervisor installations
    if not is_hassio(hass) and KEY_DATA_LOGGING in hass.data:
        tools.append(SystemLogGetLogsTool({"core": "Home Assistant"}, ["core"]))
    return LLMTools(tools=tools)
