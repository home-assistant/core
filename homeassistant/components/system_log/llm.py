"""LLM tools for the system_log integration."""

from typing import override

import voluptuous as vol

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import LLM_API_MANAGEMENT, LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType, JsonValueType

from . import DOMAIN, LogErrorHandler


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
                description="Filter by log level (e.g. 'error', 'warning', 'critical'). Case-insensitive.",
            ): cv.string,
            vol.Optional(
                "logger",
                description=(
                    "Filter by integration domain or logger name (case-insensitive "
                    "substring match, e.g. 'zwave_js', 'hue', 'automation')."
                ),
            ): cv.string,
            vol.Optional(
                "limit",
                description="Maximum number of log entries to return (default: 10, max: 50).",
                default=10,
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
        if llm_context.context and llm_context.context.user_id:
            user = await hass.auth.async_get_user(llm_context.context.user_id)
            if user is None or not user.is_admin:
                return {
                    "success": False,
                    "error": "Unauthorized: Admin access is required to view system logs.",
                }

        handler: LogErrorHandler | None = hass.data.get(DOMAIN)
        if handler is None:
            return {
                "success": False,
                "error": "System log integration is not loaded.",
            }

        args = self.parameters(tool_input.tool_args)
        raw_entries = handler.records.to_list()

        if level_filter := args.get("level"):
            normalized_level = level_filter.strip().upper()
            raw_entries = [
                entry
                for entry in raw_entries
                if entry["level"].upper() == normalized_level
            ]

        if logger_filter := args.get("logger"):
            normalized_logger = logger_filter.strip().lower()
            raw_entries = [
                entry
                for entry in raw_entries
                if normalized_logger in entry["name"].lower()
                or (
                    isinstance(entry["source"], (tuple, list))
                    and normalized_logger in str(entry["source"][0]).lower()
                )
            ]

        limit: int = args["limit"]
        raw_entries = raw_entries[:limit]

        include_traceback: bool = args["include_traceback"]
        entries: list[JsonValueType] = []
        for entry in raw_entries:
            entry_dict: JsonObjectType = {
                "name": entry["name"],
                "message": list(entry["message"]),
                "level": entry["level"],
                "source": list(entry["source"])
                if isinstance(entry["source"], (tuple, list))
                else entry["source"],
                "count": entry["count"],
                "timestamp": dt_util.utc_from_timestamp(entry["timestamp"]).isoformat(),
                "first_occurred": dt_util.utc_from_timestamp(
                    entry["first_occurred"]
                ).isoformat(),
            }
            if include_traceback and entry.get("exception"):
                entry_dict["exception"] = entry["exception"]
            entries.append(entry_dict)

        return {
            "success": True,
            "result": entries,
        }


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the system log LLM tools for the management API."""
    if api_id != LLM_API_MANAGEMENT:
        return None

    return LLMTools(tools=[SystemLogGetEntriesTool()])
