"""LLM tools for the assist_satellite integration."""

from typing import Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)

from .const import DOMAIN, AssistSatelliteService, AssistSatelliteServiceArgument
from .intent import async_get_broadcast_entity_ids


class BroadcastTool(Tool):
    """LLM Tool that broadcasts a message on Assist satellites."""

    name = f"{DOMAIN}__broadcast"
    title = "Broadcast message"
    description = (
        "Broadcasts a message through the home on voice assistants. "
        "Give an area or a floor to broadcast only there."
    )
    parameters = probatio.Schema(
        {
            probatio.Required("message"): cv.string,
            probatio.Optional(
                "area", description="Name of the area to broadcast in"
            ): cv.string,
            probatio.Optional(
                "floor", description="Name of the floor to broadcast on"
            ): cv.string,
        }
    )
    annotations = ToolAnnotations(destructive=False, open_world=False)
    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Broadcast a message."""
        args: dict[str, Any] = self.parameters(
            {
                key: value
                for key, value in tool_input.tool_args.items()
                if not intent.is_blank_slot_value(value)
            }
        )
        area = args.get("area")
        floor = args.get("floor")

        entity_ids = async_get_broadcast_entity_ids(hass, llm_context.device_id)
        states = [
            state for entity_id in entity_ids if (state := hass.states.get(entity_id))
        ]

        if area or floor:
            constraints = intent.MatchTargetsConstraints(
                area_name=area, floor_name=floor
            )
            # The matcher searches all states when it gets an empty list.
            if not states:
                raise intent.MatchFailedError(
                    result=intent.MatchTargetsResult(
                        False,
                        intent.MatchFailedReason.AREA
                        if area
                        else intent.MatchFailedReason.FLOOR,
                    ),
                    constraints=constraints,
                )
            # Satellites are matched without the assistant, because the user
            # rarely exposes them.
            result = intent.async_match_targets(hass, constraints, states=states)
            if not result.is_match:
                raise intent.MatchFailedError(result=result, constraints=constraints)
            states = result.states

        await hass.services.async_call(
            DOMAIN,
            AssistSatelliteService.ANNOUNCE,
            {AssistSatelliteServiceArgument.MESSAGE: args["message"]},
            context=llm_context.context,
            target={ATTR_ENTITY_ID: [state.entity_id for state in states]},
        )
        return ToolResult(data={"satellites": [state.name for state in states]})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the broadcast LLM tool."""
    if api_id != LLM_API_ASSIST:
        return None
    return LLMTools(tools=[BroadcastTool()])
