"""The LLM integration.

Owns the Assist API and the LLM tools platform: integrations contribute tools
to the LLM APIs through an ``<integration>/llm.py`` platform with an
``async_get_tools`` hook. The platforms are loaded lazily and queried per
request. The framework (``Tool``, the API base classes) lives in
``homeassistant.helpers.llm``.
"""

from dataclasses import dataclass
import logging
from typing import Protocol, override

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.helpers.llm import (
    API,
    LLM_API_ASSIST,
    APIInstance,
    LLMContext,
    Tool,
    async_register_api,
    selector_serializer,
)
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
    def async_get_tools(
        self, hass: HomeAssistant, llm_context: LLMContext, api_id: str
    ) -> LLMTools | None:
        """Return the integration's LLM tools for the given context and API.

        Return None when the integration has nothing for the given API.
        """


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LLM integration."""
    hass.data[DATA_PLATFORMS] = LazyIntegrationPlatforms(
        hass, DOMAIN, _process_llm_tools_platform
    )
    async_register_api(hass, AssistAPI(hass))
    return True


@callback
def _process_llm_tools_platform(
    hass: HomeAssistant, domain: str, platform: LLMToolsPlatformProtocol
) -> LLMToolsPlatformProtocol:
    """Process an integration's LLM tools platform."""
    return platform


async def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools:
    """Return the tools and merged prompt from all integration platforms."""
    platforms = await hass.data[DATA_PLATFORMS].async_get_platforms()

    tools: list[Tool] = []
    prompts: list[str] = []
    # Sort by domain so the tool and prompt order is independent of load order.
    for domain, platform in sorted(platforms.items()):
        try:
            result = platform.async_get_tools(hass, llm_context, api_id)
        except Exception:
            _LOGGER.exception("Error getting tools from LLM platform %s", domain)
            continue
        if result is None:
            continue
        tools.extend(result.tools)
        if result.prompt:
            prompts.append(result.prompt)
    return LLMTools(tools=tools, prompt="\n".join(prompts) if prompts else None)


class AssistAPI(API):
    """API exposing Assist API to LLMs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the class."""
        super().__init__(
            hass=hass,
            id=LLM_API_ASSIST,
            name="Assist",
        )

    @override
    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the instance of the API.

        The tools and the prompt are both contributed by the LLM tools
        platforms; this API only aggregates them.
        """
        llm_tools = await async_get_tools(self.hass, llm_context, self.id)

        return APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=llm_tools.tools,
            custom_serializer=selector_serializer,
        )
