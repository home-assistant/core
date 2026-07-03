"""LLM tools for the calendar integration."""

from datetime import timedelta
from typing import cast, override

import voluptuous as vol

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.llm import LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from . import SERVICE_GET_EVENTS
from .const import DOMAIN


class CalendarGetEventsTool(Tool):
    """LLM Tool allowing querying a calendar."""

    name = "calendar_get_events"
    description = (
        "Get events from a calendar. "
        "When asked if something happens, search the whole week."
    )
    parameters = vol.Schema(
        {
            vol.Required("calendar"): cv.string,
            vol.Required("range"): vol.In(["today", "week"]),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Query a calendar."""
        data = self.parameters(tool_input.tool_args)
        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["calendar"],
                domains=[DOMAIN],
                assistant=llm_context.assistant,
            ),
        )
        if not result.is_match:
            return {"success": False, "error": "Calendar not found"}

        entity_id = result.states[0].entity_id
        if data["range"] == "today":
            start = dt_util.now()
            end = dt_util.start_of_local_day() + timedelta(days=1)
        elif data["range"] == "week":
            start = dt_util.now()
            end = dt_util.start_of_local_day() + timedelta(days=7)

        service_data = {
            "entity_id": entity_id,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        }

        service_result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_EVENTS,
            service_data,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )

        events = [
            event if "T" in event["start"] else {**event, "all_day": True}
            for event in cast(dict, service_result)[entity_id]["events"]
        ]

        return {"success": True, "result": events}


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return the calendar LLM tools when a calendar is exposed."""
    if not llm_context.assistant:
        return LLMTools(tools=[])

    if not any(
        async_should_expose(hass, llm_context.assistant, state.entity_id)
        for state in hass.states.async_all(DOMAIN)
    ):
        return LLMTools(tools=[])

    return LLMTools(tools=[CalendarGetEventsTool()])
