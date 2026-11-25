"""LLM tools for the automation integration."""

from datetime import datetime
from typing import override

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
from homeassistant.util.json import JsonObjectType, JsonValueType

from . import ATTR_LAST_TRIGGERED
from .const import DATA_COMPONENT, DOMAIN

_LIMIT = 50


class ListAutomationsTool(Tool):
    """LLM Tool to list the automations."""

    name = "automation__list_automations"
    title = "List automations"
    description = (
        "List the automations, sorted by name, with their state, when they were "
        "last triggered and their description. An automation that is off does not "
        "run, and one that is unavailable has an error in its configuration. "
        f"Returns at most {_LIMIT} automations per call."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "offset",
                description=(
                    "Number of automations to skip. Use the next_offset of the "
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
        """Return a page of the automations."""
        offset: int = self.parameters(tool_input.tool_args)["offset"]
        states = sorted(
            hass.states.async_all(DOMAIN),
            key=lambda state: (state.name.casefold(), state.entity_id),
        )
        component = hass.data.get(DATA_COMPONENT)

        automations: list[JsonValueType] = []
        for state in states[offset : offset + _LIMIT]:
            last_triggered = state.attributes.get(ATTR_LAST_TRIGGERED)
            automation: JsonObjectType = {
                "entity_id": state.entity_id,
                "name": state.name,
                "state": state.state,
                "last_triggered": last_triggered.isoformat()
                if isinstance(last_triggered, datetime)
                else None,
            }
            if (
                component is not None
                and (entity := component.get_entity(state.entity_id)) is not None
                and entity.raw_config
                and (description := entity.raw_config.get("description"))
            ):
                automation["description"] = description
            automations.append(automation)

        result: JsonObjectType = {"automations": automations, "total": len(states)}
        if (next_offset := offset + _LIMIT) < len(states):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the automation LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[ListAutomationsTool()])
