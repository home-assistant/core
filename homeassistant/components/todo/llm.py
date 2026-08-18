"""LLM tools for the todo integration."""

from operator import attrgetter
from typing import Any, cast, override

import voluptuous as vol

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    Tool,
    ToolInput,
)
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, TodoServices
from .intent import (
    INTENT_LIST_ADD_ITEM,
    INTENT_LIST_COMPLETE_ITEM,
    INTENT_LIST_REMOVE_ITEM,
)

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = (INTENT_LIST_ADD_ITEM, INTENT_LIST_COMPLETE_ITEM, INTENT_LIST_REMOVE_ITEM)


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

    def __init__(self, todo_lists: list[str]) -> None:
        """Init the get items tool."""
        self.parameters = vol.Schema(
            {
                vol.Required("todo_list"): vol.In(todo_lists),
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
        status = data["status"]
        # "all" means no status filter, which returns every item.
        if status != "all":
            service_data["status"] = status
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
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the todo LLM tools when a to-do list is exposed."""
    if api_id != LLM_API_ASSIST:
        return None

    entity_registry = er.async_get(hass)
    names: list[str] = []
    for state in sorted(hass.states.async_all(DOMAIN), key=attrgetter("name")):
        if not async_should_expose(hass, llm_context.assistant, state.entity_id):
            continue
        entity_entry = entity_registry.async_get(state.entity_id)
        names.extend(intent.async_get_entity_aliases(hass, entity_entry, state=state))

    if not names:
        return None

    tools: list[Tool] = [TodoGetItemsTool(names)]
    tools.extend(
        IntentTool(handler.intent_type, handler)
        for handler in intent.async_get(hass)
        if handler.intent_type in LLM_INTENTS
    )
    return LLMTools(tools=tools)
