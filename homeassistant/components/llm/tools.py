"""Tools for the LLM integration."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.llm import (
    NO_ENTITIES_PROMPT,
    LLMContext,
    Tool,
    ToolInput,
    async_get_exposed_entities,
)
from homeassistant.util import dt as dt_util, yaml as yaml_util
from homeassistant.util.json import JsonObjectType

DYNAMIC_CONTEXT_PROMPT = (
    "You ARE equipped to answer questions about the"
    " current state of\n"
    "the home using the `GetLiveContext` tool."
    " This is a primary function."
    " Do not state you lack the\n"
    "functionality if the question requires live data.\n"
    "If the user asks about device existence/type"
    ' (e.g., "Do I have lights in the bedroom?"):'
    " Answer\n"
    "from the static context below.\n"
    "If the user asks about the CURRENT state, value,"
    ' or mode (e.g., "Is the lock locked?",\n'
    '"Is the fan on?",'
    ' "What mode is the thermostat in?",'
    ' "What is the temperature outside?"):\n'
    "    1.  Recognize this requires live data.\n"
    "    2.  You MUST call `GetLiveContext`."
    " This tool will provide the needed real-time"
    " information (like temperature from the local"
    " weather, lock status, etc.).\n"
    "    3.  Use the tool's response** to answer the"
    " user accurately"
    ' (e.g., "The temperature outside is'
    ' [value from tool].").\n'
    "For general knowledge questions not about the"
    " home: Answer truthfully from internal"
    " knowledge.\n"
)


class GetDateTimeTool(Tool):
    """Tool for getting the current date and time."""

    name = "GetDateTime"
    description = "Provides the current date and time."

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the current date and time."""
        now = dt_util.now()

        return {
            "success": True,
            "result": {
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": now.strftime("%Z"),
                "weekday": now.strftime("%A"),
            },
        }


def _live_context_match_error(
    match_result: intent.MatchTargetsResult,
    name_filter: str | None,
    area_filter: str | None,
    domain_filter: list[str] | None,
) -> str:
    """Build an actionable error message for a failed GetLiveContext match."""
    reason = match_result.no_match_reason
    if reason is intent.MatchFailedReason.INVALID_AREA:
        return f"Area '{match_result.no_match_name}' does not exist"
    if reason is intent.MatchFailedReason.NAME:
        return f"No exposed entities matched name '{name_filter}'"
    if reason is intent.MatchFailedReason.AREA:
        return f"No exposed entities found in area '{area_filter}'"
    if reason is intent.MatchFailedReason.DOMAIN:
        domains = ", ".join(domain_filter) if domain_filter else ""
        return f"No exposed entities found in domain(s): {domains}"
    return "No entities matched the provided filter"


class GetLiveContextTool(Tool):
    """Tool for getting the current state of exposed entities.

    This returns state for all entities that have been exposed to
    the assistant. This is different than the GetState intent, which
    returns state for entities based on intent parameters.
    """

    name = "GetLiveContext"
    description = (
        "Provides real-time information about the"
        " CURRENT state, value, or mode of devices,"
        " sensors, entities, or areas. "
        "Use this tool for: "
        "1. Answering questions about current"
        " conditions (e.g., 'Is the light on?'). "
        "2. As the first step in conditional actions"
        " (e.g., 'If the weather is rainy, turn off"
        " sprinklers' requires checking the weather"
        " first). "
        "You may filter for devices by name, domain,"
        " and area, including combining those"
        " filters. "
        "Prefer filtering by domain when searching"
        " for multiple devices of the same type."
    )
    parameters = vol.Schema(
        {
            vol.Optional(
                "name",
                description="Filter entities by name or alias (case-insensitive).",
            ): cv.string,
            vol.Optional(
                "domain",
                description=(
                    "Filter entities by domain"
                    " (e.g. 'light', 'sensor')."
                    " Accepts a single domain or a list."
                ),
            ): vol.Any(cv.string, [cv.string]),
            vol.Optional(
                "area",
                description="Filter entities by area name or alias (case-insensitive).",
            ): cv.string,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the current state of exposed entities."""
        if llm_context.assistant is None:
            # Note this doesn't happen in practice since this tool won't be
            # exposed if no assistant is configured.
            return {"success": False, "error": "No assistant configured"}

        args = self.parameters(tool_input.tool_args)
        exposed_entities = async_get_exposed_entities(
            hass, llm_context.assistant, include_state=True
        )

        if not exposed_entities["entities"]:
            return {"success": False, "error": NO_ENTITIES_PROMPT}

        name_filter = args.get("name")
        area_filter = args.get("area")
        domain_filter = args.get("domain")

        if isinstance(domain_filter, str):
            domain_filter = [domain_filter]

        if domain_filter is not None:
            domain_filter = [
                normalized_domain
                for domain in domain_filter
                if (normalized_domain := domain.strip().lower())
            ]

        if name_filter or area_filter or domain_filter:
            exposed_states = [
                state
                for entity_id in exposed_entities["entities"]
                if (state := hass.states.get(entity_id)) is not None
            ]
            match_result = intent.async_match_targets(
                hass,
                intent.MatchTargetsConstraints(
                    name=name_filter,
                    area_name=area_filter,
                    domains=domain_filter,
                    # This tool only returns context, so multiple entities
                    # sharing a name (e.g. "AC" in two areas) should all be
                    # returned rather than failing as an ambiguous match.
                    allow_duplicate_names=True,
                ),
                states=exposed_states,
            )

            if not match_result.is_match:
                return {
                    "success": False,
                    "error": _live_context_match_error(
                        match_result, name_filter, area_filter, domain_filter
                    ),
                }

            matched_ids = {state.entity_id for state in match_result.states}
            entities = [
                info
                for entity_id, info in exposed_entities["entities"].items()
                if entity_id in matched_ids
            ]
        else:
            entities = list(exposed_entities["entities"].values())

        prompt = [
            "Live Context: An overview of the areas"
            " and the devices in this smart home:",
            yaml_util.dump(entities),
        ]
        return {
            "success": True,
            "result": "\n".join(prompt),
        }
