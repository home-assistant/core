"""Tools for the LLM integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.llm import LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType


class GetDateTimeTool(Tool):
    """Tool for getting the current date and time."""

    name = "GetDateTime"
    description = "Provides the current date and time."

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
