"""The LLM integration.

Owns the LLM tools platform: integrations contribute tools to the LLM APIs
through an ``<integration>/llm.py`` platform with an ``async_get_tools`` hook.
The platforms are loaded lazily and queried per request. The framework
(``Tool``, the APIs) lives in ``homeassistant.helpers.llm``.
"""

from dataclasses import dataclass
import logging
from typing import Protocol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.helpers.llm import LLMContext, Tool
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

DATA_PLATFORMS: HassKey[LazyIntegrationPlatforms[LLMToolsPlatformProtocol]] = HassKey(
    "llm_platforms"
)


@dataclass(slots=True)
class LLMTools:
    """Tools and an optional prompt fragment contributed by a platform."""

    tools: list[Tool]
    prompt: str | None = None


class LLMToolsPlatformProtocol(Protocol):
    """Define the format that LLM tools platforms can have."""

    @callback
    def async_get_tools(self, hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
        """Return the integration's LLM tools for the given context."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LLM integration."""
    hass.data[DATA_PLATFORMS] = LazyIntegrationPlatforms(
        hass, DOMAIN, _process_llm_tools_platform
    )
    return True


@callback
def _process_llm_tools_platform(
    hass: HomeAssistant, domain: str, platform: LLMToolsPlatformProtocol
) -> LLMToolsPlatformProtocol:
    """Process an integration's LLM tools platform."""
    return platform


async def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return the tools and merged prompt from all integration platforms."""
    platforms = await hass.data[DATA_PLATFORMS].async_get_platforms()

    tools: list[Tool] = []
    prompts: list[str] = []
    # Sort by domain so the tool and prompt order is independent of load order.
    for domain, platform in sorted(platforms.items()):
        try:
            result = platform.async_get_tools(hass, llm_context)
        except Exception:
            _LOGGER.exception("Error getting tools from LLM platform %s", domain)
            continue
        tools.extend(result.tools)
        if result.prompt:
            prompts.append(result.prompt)
    return LLMTools(tools=tools, prompt="\n".join(prompts) if prompts else None)
