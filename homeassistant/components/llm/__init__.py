"""The LLM integration."""

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
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

DATA_PLATFORMS: HassKey[LazyIntegrationPlatforms[LLMToolsPlatformProtocol]] = HassKey(
    "llm_platforms"
)
DATA_WARNED_DUPLICATE_TOOLS: HassKey[set[str]] = HassKey("llm_warned_duplicate_tools")


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
    hass.data[DATA_WARNED_DUPLICATE_TOOLS] = set()
    async_register_api(hass, AssistAPI(hass))
    async_setup_ws_api(hass)
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
    # LLM APIs reject duplicate tool names, so the first platform to contribute
    # a name wins. Remember the source so the warning can name both platforms.
    tool_sources: dict[str, str] = {}
    collided: set[str] = set()
    warned = hass.data[DATA_WARNED_DUPLICATE_TOOLS]
    # Sort by domain so the tool and prompt order is independent of load order.
    for domain, platform in sorted(platforms.items()):
        try:
            result = platform.async_get_tools(hass, llm_context, api_id)
        except Exception:
            _LOGGER.exception("Error getting tools from LLM platform %s", domain)
            continue
        if result is None:
            continue
        for tool in result.tools:
            if (source := tool_sources.get(tool.name)) is not None:
                collided.add(tool.name)
                # This runs on every conversation turn, so only warn once per name.
                if tool.name not in warned:
                    warned.add(tool.name)
                    _LOGGER.warning(
                        "Ignoring LLM tool %s from platform %s; platform %s already"
                        " provides a tool with that name",
                        tool.name,
                        domain,
                        source,
                    )
                continue
            tool_sources[tool.name] = domain
            tools.append(tool)
        if result.prompt:
            prompts.append(result.prompt)
    # Forget names that no longer collide so the warning returns if they do again.
    warned.difference_update(tool_sources.keys() - collided)
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
        """Return the instance of the API."""
        llm_tools = await async_get_tools(self.hass, llm_context, self.id)

        return APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=llm_tools.tools,
            custom_serializer=selector_serializer,
        )
