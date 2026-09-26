"""Home Assistant tool host for pipeline processors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType


@dataclass(frozen=True, slots=True)
class PipelineToolHost:
    """Run-scoped tools exposed to a pipeline processor."""

    _api_instance: llm.APIInstance

    @classmethod
    async def async_create(
        cls,
        hass: HomeAssistant,
        api_id: str | list[str],
        llm_context: llm.LLMContext,
    ) -> PipelineToolHost:
        """Create a tool host for one pipeline run."""
        return cls(await llm.async_get_api(hass, api_id, llm_context))

    @property
    def api_prompt(self) -> str:
        """Return the prompt associated with the selected APIs."""
        return self._api_instance.api_prompt

    @property
    def tools(self) -> tuple[llm.Tool, ...]:
        """Return the tools available to the processor."""
        return tuple(self._api_instance.tools)

    @property
    def custom_serializer(self) -> Callable[[Any], Any] | None:
        """Return the serializer used for tool schemas."""
        return self._api_instance.custom_serializer

    async def async_call_tool(self, tool_input: llm.ToolInput) -> JsonObjectType:
        """Validate and call a Home Assistant LLM tool."""
        return await self._api_instance.async_call_tool(tool_input)
