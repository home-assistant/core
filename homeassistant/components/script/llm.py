"""LLM tools for the script integration."""

from operator import attrgetter

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.llm import ActionTool, LLMContext, Tool

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

        self.name = script_name
        if self.name[0].isdigit():
            self.name = "_" + self.name


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return a script LLM tool for each exposed script."""
    tools: list[Tool] = [
        ScriptTool(hass, state.entity_id)
        for state in sorted(hass.states.async_all(DOMAIN), key=attrgetter("name"))
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    ]
    return LLMTools(tools=tools)
