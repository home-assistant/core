"""LLM tools for the system_log integration."""

from collections.abc import Callable
from typing import Any, override

import voluptuous as vol

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import LLM_API_MANAGEMENT, LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from . import DOMAIN, LogErrorHandler

_LOG_LEVELS = ["error", "warning", "critical"]
_DEFAULT_LIMIT = 25


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

    if logger:
        logger_lower = logger.strip().lower()
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
    description = (
        "Retrieve recent system log errors and warnings from Home Assistant. "
        "Can filter by log level, domain or logger name, and choose whether "
        "to include full exception tracebacks."
    )
    parameters = vol.Schema(
        {
            vol.Optional(
                "level",
                description="Filter by log level. Allowed values: 'error', 'warning', 'critical'.",
            ): vol.All(cv.string, vol.Lower, vol.In(_LOG_LEVELS)),
            vol.Optional(
                "logger",
                description=(
                    "Filter by integration domain or logger name (case-insensitive "
                    "substring match, e.g. 'zwave_js', 'hue', 'automation')."
                ),
            ): cv.string,
            vol.Optional(
                "limit",
                description=f"Maximum number of log entries to return (default: {_DEFAULT_LIMIT}, max: 50).",
                default=_DEFAULT_LIMIT,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            vol.Optional(
                "include_traceback",
                description=(
                    "Whether to include full Python exception stack traces in the "
                    "returned entries (default: false)."
                ),
                default=False,
            ): cv.boolean,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Query the system log."""
        handler: LogErrorHandler | None = hass.data.get(DOMAIN)
        if handler is None:
            return {
                "success": False,
                "error": "System log integration is not loaded.",
            }

        args = self.parameters(tool_input.tool_args)
        filtered_entries = _filter_log_entries(
            handler.records.to_list(),
            level=args.get("level"),
            logger=args.get("logger"),
            limit=args["limit"],
        )
        include_traceback: bool = args["include_traceback"]
        return {
            "success": True,
            "result": [
                _format_entry(entry, include_traceback) for entry in filtered_entries
            ],
        }


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the system log LLM tools for the management API."""
    if api_id != LLM_API_MANAGEMENT:
        return None

    return LLMTools(tools=[SystemLogGetEntriesTool()])
