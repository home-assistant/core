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

from homeassistant.components.intent import async_device_supports_timers
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    floor_registry as fr,
)
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.helpers.llm import (
    API,
    LLM_API_ASSIST,
    NO_ENTITIES_PROMPT,
    APIInstance,
    LLMContext,
    Tool,
    _get_exposed_entities,
    async_register_api,
    selector_serializer,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import yaml as yaml_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

DATA_PLATFORMS: HassKey[LazyIntegrationPlatforms[LLMToolsPlatformProtocol]] = HassKey(
    "llm_platforms"
)

DEVICE_CONTROL_TOOL_USAGE_PROMPT = (
    "When controlling Home Assistant always call the intent tools. "
    "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
    "When controlling a device, prefer passing just name and domain. "
    "When controlling an area, prefer passing just area name and domain."
)

DYNAMIC_CONTEXT_PROMPT = (
    "You ARE equipped to answer questions about the"
    " current state of\n"
    "the home using the `GetLiveContext` tool."
    " This is a primary function."
    " Do not state you lack the\n"
    "functionality if the question requires live data.\n"
    "If the user asks about device existence/type"
    ' (e.g., "Do I have lights in the bedroom?"):'
    " Answer\n"
    "from the static context below.\n"
    "If the user asks about the CURRENT state, value,"
    ' or mode (e.g., "Is the lock locked?",\n'
    '"Is the fan on?",'
    ' "What mode is the thermostat in?",'
    ' "What is the temperature outside?"):\n'
    "    1.  Recognize this requires live data.\n"
    "    2.  You MUST call `GetLiveContext`."
    " This tool will provide the needed real-time"
    " information (like temperature from the local"
    " weather, lock status, etc.).\n"
    "    3.  Use the tool's response** to answer the"
    " user accurately"
    ' (e.g., "The temperature outside is'
    ' [value from tool].").\n'
    "For general knowledge questions not about the"
    " home: Answer truthfully from internal"
    " knowledge.\n"
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
        """Return the instance of the API."""
        if llm_context.assistant:
            exposed_entities: dict | None = _get_exposed_entities(
                self.hass, llm_context.assistant, include_state=False
            )
        else:
            exposed_entities = None

        llm_tools = await async_get_tools(self.hass, llm_context, self.id)

        return APIInstance(
            api=self,
            api_prompt=self._async_get_api_prompt(
                llm_context, exposed_entities, llm_tools.prompt
            ),
            llm_context=llm_context,
            tools=llm_tools.tools,
            custom_serializer=selector_serializer,
        )

    @callback
    def _async_get_api_prompt(
        self,
        llm_context: LLMContext,
        exposed_entities: dict | None,
        extra_prompt: str | None,
    ) -> str:
        prompt_parts: list[str | None]
        if not exposed_entities or not exposed_entities["entities"]:
            prompt_parts = [NO_ENTITIES_PROMPT]
        else:
            prompt_parts = [
                DEVICE_CONTROL_TOOL_USAGE_PROMPT,
                DYNAMIC_CONTEXT_PROMPT,
                *self._async_get_exposed_entities_prompt(exposed_entities),
                self._async_get_voice_satellite_area_prompt(llm_context),
                self._async_get_no_timer_prompt(llm_context),
            ]

        if extra_prompt:
            prompt_parts.append(extra_prompt)

        # Filter out None and empty strings before joining
        return "\n".join([part for part in prompt_parts if part])

    @callback
    def _async_get_no_timer_prompt(self, llm_context: LLMContext) -> str | None:
        if not llm_context.device_id or not async_device_supports_timers(
            self.hass, llm_context.device_id
        ):
            return "This device is not able to start timers."
        return None

    @callback
    def _async_get_voice_satellite_area_prompt(self, llm_context: LLMContext) -> str:
        """Return the area prompt for the voice satellite."""
        floor: fr.FloorEntry | None = None
        area: ar.AreaEntry | None = None
        extra = ""
        if llm_context.device_id:
            device_reg = dr.async_get(self.hass)
            device = device_reg.async_get(llm_context.device_id)

            if device:
                area_reg = ar.async_get(self.hass)
                if device.area_id and (area := area_reg.async_get_area(device.area_id)):
                    floor_reg = fr.async_get(self.hass)
                    if area.floor_id:
                        floor = floor_reg.async_get_floor(area.floor_id)

            extra = (
                "and all generic commands like"
                " 'turn on the lights' should target"
                " this area."
            )

        if floor and area:
            return f"You are in area {area.name} (floor {floor.name}) {extra}".strip()
        if area:
            return f"You are in area {area.name} {extra}".strip()
        return (
            "When a user asks to turn on all devices of a specific type, "
            "ask the user to specify an area, unless there"
            " is only one device of that type."
        )

    @callback
    def _async_get_exposed_entities_prompt(
        self, exposed_entities: dict | None
    ) -> list[str]:
        """Return the prompt for the API for exposed entities."""
        prompt = []

        if exposed_entities and exposed_entities["entities"]:
            prompt.append(
                "Static Context: An overview of the areas"
                " and the devices in this smart home:"
            )
            prompt.append(yaml_util.dump(list(exposed_entities["entities"].values())))

        return prompt
