"""The LLM integration.

Owns the LLM tools platform: integrations contribute tools to the LLM APIs
through an ``<integration>/llm.py`` platform with an ``async_setup_tools`` hook,
discovered here, and register them with ``async_register_tool_provider``. The
framework (``Tool``, the APIs) lives in ``homeassistant.helpers.llm``; this
integration owns the registry and lifecycle, mirroring the ``intent``
helper/integration split.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.llm import LLMContext, Tool
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass(slots=True)
class LLMTools:
    """Tools and an optional prompt fragment contributed by a provider."""

    tools: list[Tool]
    prompt: str | None = None


type LLMToolProvider = Callable[[HomeAssistant, LLMContext], LLMTools]


_TOOL_PROVIDERS: HassKey[list[LLMToolProvider]] = HassKey("llm_tool_providers")


@callback
def async_register_tool_provider(
    hass: HomeAssistant,
    provider: LLMToolProvider,
) -> Callable[[], None]:
    """Register a provider that contributes tools to the LLM API.

    The provider is evaluated per request with the ``LLMContext`` and returns
    the tools (and an optional prompt fragment) to expose.
    """
    providers = hass.data.setdefault(_TOOL_PROVIDERS, [])
    providers.append(provider)

    @callback
    def unregister() -> None:
        """Unregister the tool provider."""
        providers.remove(provider)

    return unregister


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return the tools and merged prompt from all registered providers."""
    providers = hass.data.get(_TOOL_PROVIDERS)
    if not providers:
        return LLMTools(tools=[])

    tools: list[Tool] = []
    prompts: list[str] = []
    for provider in providers:
        result = provider(hass, llm_context)
        tools.extend(result.tools)
        if result.prompt:
            prompts.append(result.prompt)
    return LLMTools(tools=tools, prompt="\n".join(prompts) if prompts else None)


class LLMToolsPlatformProtocol(Protocol):
    """Define the format that LLM tools platforms can have."""

    async def async_setup_tools(self, hass: HomeAssistant) -> None:
        """Set up the integration's LLM tools."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LLM integration."""
    await async_process_integration_platforms(
        hass, DOMAIN, _async_process_llm_tools_platform
    )
    return True


async def _async_process_llm_tools_platform(
    hass: HomeAssistant, domain: str, platform: LLMToolsPlatformProtocol
) -> None:
    """Register the LLM tools of an integration."""
    await platform.async_setup_tools(hass)
