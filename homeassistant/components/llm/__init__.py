"""The LLM integration.

Owns the LLM tools platform: integrations contribute tools to the LLM APIs
through an ``<integration>/llm.py`` platform with an ``async_setup_tools`` hook,
discovered here. The framework (registry, ``Tool``, the APIs) lives in
``homeassistant.helpers.llm``; this integration owns the lifecycle, mirroring the
``intent`` helper/integration split.
"""

from typing import Protocol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .intents import intent_tools
from .tools import DYNAMIC_CONTEXT_PROMPT, GetDateTimeTool, GetLiveContextTool

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class LLMToolsPlatformProtocol(Protocol):
    """Define the format that LLM tools platforms can have."""

    async def async_setup_tools(self, hass: HomeAssistant) -> None:
        """Set up the integration's LLM tools."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LLM integration."""
    llm.async_register_tool_provider(
        hass, intent_tools, apis={llm.LLM_API_ASSIST: None}
    )
    llm.async_register_tool(hass, GetDateTimeTool(), apis={llm.LLM_API_ASSIST: None})
    llm.async_register_tool_provider(
        hass, _live_context_tools, apis={llm.LLM_API_ASSIST: None}
    )
    await async_process_integration_platforms(
        hass, DOMAIN, _async_process_llm_tools_platform
    )
    return True


@callback
def _live_context_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> llm.LLMTools:
    """Return the live-context tool and its prompt when entities are exposed."""
    if llm_context.assistant is None:
        return llm.LLMTools(tools=[])

    exposed = llm.async_get_exposed_entities(
        hass, llm_context.assistant, include_state=False
    )
    exposed_domains = {info["domain"] for info in exposed["entities"].values()}
    if not exposed_domains:
        return llm.LLMTools(tools=[])

    return llm.LLMTools(tools=[GetLiveContextTool()], prompt=DYNAMIC_CONTEXT_PROMPT)


async def _async_process_llm_tools_platform(
    hass: HomeAssistant, domain: str, platform: LLMToolsPlatformProtocol
) -> None:
    """Register the LLM tools of an integration."""
    await platform.async_setup_tools(hass)
