"""LLM tools for the todo integration."""

from typing import Any, cast, override

import slugify as unicode_slug
import voluptuous as vol

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.llm import IntentTool, LLMContext, Tool, ToolInput
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, TodoServices

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = ("HassListAddItem", "HassListCompleteItem", "HassListRemoveItem")


class TodoGetItemsTool(Tool):
    """LLM Tool allowing querying a to-do list."""

    name = "todo_get_items"
    description = (
        "Query a to-do list to find out what items are on it. "
        "Use this to answer questions like "
        "'What's on my task list?' or "
        "'Read my grocery list'. "
        "Filters items by status (needs_action, completed, all)."
    )

    parameters = vol.Schema(
        {
            vol.Required("todo_list"): cv.string,
            vol.Optional(
                "status",
                description=(
                    "Filter returned items by status,"
                    " by default returns incomplete"
                    " items"
                ),
                default="needs_action",
            ): vol.In(["needs_action", "completed", "all"]),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Query a to-do list."""
        data = self.parameters(tool_input.tool_args)
        result = intent.async_match_targets(
            hass,
            intent.MatchTargetsConstraints(
                name=data["todo_list"],
                domains=[DOMAIN],
                assistant=llm_context.assistant,
            ),
        )
        if not result.is_match:
            return {"success": False, "error": "To-do list not found"}
        entity_id = result.states[0].entity_id
        service_data: dict[str, Any] = {"entity_id": entity_id}
        if status := data.get("status"):
            if status == "all":
                service_data["status"] = ["needs_action", "completed"]
            else:
                service_data["status"] = [status]
        service_result = await hass.services.async_call(
            DOMAIN,
            TodoServices.GET_ITEMS,
            service_data,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )
        if not service_result:
            return {"success": False, "error": "To-do list not found"}
        items = cast(dict, service_result)[entity_id]["items"]
        return {"success": True, "result": items}


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return the todo LLM tools when a to-do list is exposed."""
    if not llm_context.assistant:
        return LLMTools(tools=[])

    if not any(
        async_should_expose(hass, llm_context.assistant, state.entity_id)
        for state in hass.states.async_all(DOMAIN)
    ):
        return LLMTools(tools=[])

    handlers = {handler.intent_type: handler for handler in intent.async_get(hass)}
    tools: list[Tool] = [TodoGetItemsTool()]
    tools.extend(
        IntentTool(
            unicode_slug.slugify(intent_type, separator="_", lowercase=False),
            handlers[intent_type],
        )
        for intent_type in LLM_INTENTS
        if intent_type in handlers
    )
    return LLMTools(tools=tools)
