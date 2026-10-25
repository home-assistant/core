"""LLM tools for the script integration."""

from operator import attrgetter
from typing import override

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    ActionTool,
    LLMContext,
    Tool,
    ToolInput,
    ToolResult,
)

from .const import DOMAIN


class ScriptTool(ActionTool):
    """LLM Tool representing a Script."""

    def __init__(
        self,
        hass: HomeAssistant,
        script_entity_id: str,
    ) -> None:
        """Init the class."""
        script_name = split_entity_id(script_entity_id)[1]

        action = script_name
        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get(script_entity_id)
        if entity_entry and entity_entry.unique_id:
            action = entity_entry.unique_id

        super().__init__(hass, DOMAIN, action)

        self._entity_id = script_entity_id
        self.name = f"{DOMAIN}__{script_name}"
        # The script is named by the user, so its name is already in their
        # language.
        if state := hass.states.get(script_entity_id):
            self.title = state.name

        if entity_entry and (
            aliases := er.async_get_entity_aliases(hass, entity_entry)
        ):
            alias_text = "Aliases: " + str(sorted(aliases))
            self.description = (
                f"{self.description}. {alias_text}" if self.description else alias_text
            )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Call the script if it is still exposed."""
        # A conversation keeps its tools, so the script may have been
        # unexposed since this tool was created.
        if not async_should_expose(hass, llm_context.assistant, self._entity_id):
            raise HomeAssistantError(f"Script {self._entity_id} is not exposed")
        return await super().async_call(hass, tool_input, llm_context)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return a script LLM tool for each exposed script."""
    if api_id != LLM_API_ASSIST:
        return None

    tools: list[Tool] = [
        ScriptTool(hass, state.entity_id)
        for state in sorted(hass.states.async_all(DOMAIN), key=attrgetter("name"))
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    ]
    if not tools:
        return None
    return LLMTools(tools=tools)
