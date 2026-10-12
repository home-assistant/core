"""LLM tools for the history integration."""

from datetime import datetime, timedelta
from typing import cast, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.components.recorder import get_instance, history
from homeassistant.core import HomeAssistant, State, callback
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

_DEFAULT_PERIOD = timedelta(days=1)
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 1000


def _format_state(state: State, include_attributes: bool) -> JsonObjectType:
    """Format a single historical state for LLM consumption."""
    entry: JsonObjectType = {
        "state": state.state,
        "last_changed": dt_util.as_local(state.last_changed).isoformat(),
    }
    if include_attributes:
        entry["attributes"] = dict(state.attributes)
    return entry


def _get_history(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime,
    entity_ids: list[str],
    significant_changes_only: bool,
    include_attributes: bool,
    limit: int,
) -> JsonObjectType:
    """Fetch and format the history in the recorder executor."""
    states = history.get_significant_states(
        hass,
        start_time,
        end_time,
        entity_ids,
        significant_changes_only=significant_changes_only,
        no_attributes=not include_attributes,
    )
    result: JsonObjectType = {}
    for entity_id in entity_ids:
        entity_states = cast(list[State], states.get(entity_id, []))
        result[entity_id] = {
            "total": len(entity_states),
            # Keep the most recent changes when the limit is exceeded.
            "states": [
                _format_state(state, include_attributes)
                for state in entity_states[-limit:]
            ],
        }
    return result


def _parse_time(value: str) -> datetime | None:
    """Parse a datetime string, assuming local time when no offset is given."""
    if (parsed := dt_util.parse_datetime(value)) is None:
        return None
    return dt_util.as_utc(parsed)


class GetHistoryTool(Tool):
    """LLM Tool allowing querying the state history of entities."""

    name = "history__get_history"
    title = "Get history"
    description = (
        "Retrieve the recorded state history of one or more entities. Use this to "
        "answer questions about past values, when something changed, or how a value "
        "evolved over time. "
        "The first state of each entity is its state at the start of the period. "
        "If more state changes exist than the limit, only the most recent ones "
        "are returned and 'total' shows how many were recorded."
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
                "significant_changes_only",
                description=(
                    "Only return significant state changes. Set to false to also "
                    "include attribute-only changes (default: true)."
                ),
                default=True,
            ): probatio.All(probatio.Boolean(), bool),
            probatio.Optional(
                "include_attributes",
                description="Whether to include the state attributes (default: false).",
                default=False,
            ): probatio.All(probatio.Boolean(), bool),
            probatio.Optional(
                "limit",
                description=f"Maximum number of states to return per entity (default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT}).",
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
        """Query the state history."""
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

        result = await get_instance(hass).async_add_executor_job(
            _get_history,
            hass,
            start_time,
            end_time,
            args["entity_ids"],
            args["significant_changes_only"],
            args["include_attributes"],
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
