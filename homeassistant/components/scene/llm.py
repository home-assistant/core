"""LLM tools for the scene integration."""

from typing import override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
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

from .const import DOMAIN

_LIMIT = 50


class ListScenesTool(Tool):
    """LLM Tool to list the scenes."""

    name = "scene__list_scenes"
    title = "List scenes"
    description = (
        "List the scenes, sorted by name, with when they were last activated. "
        f"Returns at most {_LIMIT} scenes per call."
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
                    "Number of scenes to skip. Use the next_offset of the previous "
                    "result."
                ),
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return a page of the scenes."""
        offset: int = self.parameters(tool_input.tool_args)["offset"]
        states = sorted(
            hass.states.async_all(DOMAIN),
            key=lambda state: (state.name.casefold(), state.entity_id),
        )

        scenes: list[JsonValueType] = []
        for state in states[offset : offset + _LIMIT]:
            # The state of a scene is the time it was last activated
            scene: JsonObjectType = {
                "entity_id": state.entity_id,
                "name": state.name,
                "last_activated": None
                if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                else state.state,
            }
            if state.state == STATE_UNAVAILABLE:
                scene["available"] = False
            scenes.append(scene)

        result: JsonObjectType = {"scenes": scenes, "total": len(states)}
        if (next_offset := offset + _LIMIT) < len(states):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the scene LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[ListScenesTool()])
