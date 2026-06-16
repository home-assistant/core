"""LLM tools for the todo integration."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent, llm
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, TodoServices


async def async_setup_tools(hass: HomeAssistant) -> None:
    """Set up the todo LLM tools."""
    llm.async_register_tool_provider(hass, _todo_tools, apis={llm.LLM_API_ASSIST: None})


@callback
def _todo_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> llm.LLMTools:
    """Return the todo tools for the exposed to-do lists."""
    if llm_context.assistant is None:
        return llm.LLMTools(tools=[])

    exposed = llm.async_get_exposed_entities(
        hass, llm_context.assistant, include_state=False
    )
    names = []
    for info in exposed["entities"].values():
        if info["domain"] != DOMAIN:
            continue
        names.extend(info["names"].split(", "))
    if not names:
        return llm.LLMTools(tools=[])

    return llm.LLMTools(tools=[TodoGetItemsTool(names)])


class TodoGetItemsTool(llm.Tool):
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

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
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
