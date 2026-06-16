"""LLM tools for the calendar integration."""

from datetime import timedelta
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent, llm
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from . import SERVICE_GET_EVENTS
from .const import DOMAIN


async def async_setup_tools(hass: HomeAssistant) -> None:
    """Set up the calendar LLM tools."""
    llm.async_register_tool_provider(
        hass, _calendar_tools, apis={llm.LLM_API_ASSIST: None}
    )


@callback
def _calendar_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> llm.LLMTools:
    """Return the calendar tools for the exposed calendars."""
    if llm_context.assistant is None:
        return llm.LLMTools(tools=[])

    exposed = llm.async_get_exposed_entities(
        hass, llm_context.assistant, include_state=False
    )
    if not exposed[DOMAIN]:
        return llm.LLMTools(tools=[])

    names = []
    for info in exposed[DOMAIN].values():
        names.extend(info["names"].split(", "))
    return llm.LLMTools(tools=[CalendarGetEventsTool(names)])


class CalendarGetEventsTool(llm.Tool):
    """LLM Tool allowing querying a calendar."""

    name = "calendar_get_events"
    description = (
        "Get events from a calendar. "
        "When asked if something happens, search the whole week. "
        "Results are RFC 5545 which means 'end' is exclusive."
    )

    def __init__(self, calendars: list[str]) -> None:
        """Init the get events tool."""
        self.parameters = vol.Schema(
            {
                vol.Required("calendar"): vol.In(calendars),
                vol.Required("range"): vol.In(["today", "week"]),
            }
        )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
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
