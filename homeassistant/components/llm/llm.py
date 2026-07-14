"""LLM tools provided by the llm integration."""

from typing import override

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from . import LLMTools


class GetDateTimeTool(Tool):
    """Tool for getting the current date and time."""

    name = "GetDateTime"
    description = "Provides the current date and time."

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Get the current date and time."""
        now = dt_util.now()

        return {
            "success": True,
            "result": {
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": now.strftime("%Z"),
                "weekday": now.strftime("%A"),
            },
        }


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools:
    """Return the always-available LLM tools."""
    return LLMTools(tools=[GetDateTimeTool()])
