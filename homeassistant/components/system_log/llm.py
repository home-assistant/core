"""LLM tools for the system_log integration."""

from collections.abc import Callable
from typing import Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
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

from . import DOMAIN, LogErrorHandler

_LOG_LEVELS = ["error", "warning", "critical"]
_DEFAULT_LIMIT = 25
_MAX_LIMIT = 50


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


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the system log LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[SystemLogGetEntriesTool()])
