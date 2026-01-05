"""Support for functionality to have conversations with Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Literal

from hassil.recognize import RecognizeResult
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent_manager import (
    AgentInfo,
    agent_id_validator,
    async_converse,
    async_get_agent,
    get_agent_manager,
)
from .chat_log import (
    AssistantContent,
    AssistantContentDeltaDict,
    Attachment,
    ChatLog,
    Content,
    ConverseError,
    SystemContent,
    ToolResultContent,
    ToolResultContentDeltaDict,
    UserContent,
    async_get_chat_log,
)
from .const import (
    ATTR_AGENT_ID,
    ATTR_CONVERSATION_ID,
    ATTR_LANGUAGE,
    ATTR_TEXT,
    DATA_COMPONENT,
    DOMAIN,
    HOME_ASSISTANT_AGENT,
    METADATA_CUSTOM_FILE,
    METADATA_CUSTOM_SENTENCE,
    SERVICE_PROCESS,
    SERVICE_RELOAD,
    ConversationEntityFeature,
)
from .default_agent import async_setup_default_agent
from .entity import ConversationEntity
from .http import async_setup as async_setup_conversation_http
from .models import AbstractConversationAgent, ConversationInput, ConversationResult
from .trace import ConversationTraceEventType, async_conversation_trace_append
from .util import async_get_result_from_chat_log

__all__ = [
    "DOMAIN",
    "HOME_ASSISTANT_AGENT",
    "AssistantContent",
    "AssistantContentDeltaDict",
    "Attachment",
    "ChatLog",
    "Content",
    "ConversationEntity",
    "ConversationEntityFeature",
    "ConversationInput",
    "ConversationResult",
    "ConversationTraceEventType",
    "ConverseError",
    "SystemContent",
    "ToolResultContent",
    "ToolResultContentDeltaDict",
    "UserContent",
    "async_conversation_trace_append",
    "async_converse",
    "async_get_agent_info",
    "async_get_chat_log",
    "async_get_result_from_chat_log",
    "async_set_agent",
    "async_unset_agent",
]

_LOGGER = logging.getLogger(__name__)

SERVICE_PROCESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_AGENT_ID): agent_id_validator,
        vol.Optional(ATTR_CONVERSATION_ID): cv.string,
    }
)


SERVICE_RELOAD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_AGENT_ID): agent_id_validator,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional("intents"): vol.Schema(
                    {cv.string: vol.All(cv.ensure_list, [cv.string])}
                )
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
@bind_hass
def async_set_agent(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    agent: AbstractConversationAgent,
) -> None:
    """Set the agent to handle the conversations."""
    get_agent_manager(hass).async_set_agent(config_entry.entry_id, agent)


@callback
@bind_hass
def async_unset_agent(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Unset the agent to handle the conversations."""
    get_agent_manager(hass).async_unset_agent(config_entry.entry_id)


@callback
def async_get_conversation_languages(
    hass: HomeAssistant, agent_id: str | None = None
) -> set[str] | Literal["*"]:
    """Return languages supported by conversation agents.

    If an agent is specified, returns a set of languages supported by that agent.
    If no agent is specified, return a set with the union of languages supported by
    all conversation agents.
    """
    agent_manager = get_agent_manager(hass)
    agents: list[ConversationEntity | AbstractConversationAgent]

    if agent_id:
        agent = async_get_agent(hass, agent_id)

        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Shortcut
        if agent.supported_languages == MATCH_ALL:
            return MATCH_ALL

        agents = [agent]

    else:
        agents = list(hass.data[DATA_COMPONENT].entities)
        for info in agent_manager.async_get_agent_info():
            agent = agent_manager.async_get_agent(info.id)
            assert agent is not None

            # Shortcut
            if agent.supported_languages == MATCH_ALL:
                return MATCH_ALL

            agents.append(agent)

    languages: set[str] = set()

    for agent in agents:
        for language_tag in agent.supported_languages:
            languages.add(language_tag)

    return languages


@callback
def async_get_agent_info(
    hass: HomeAssistant,
    agent_id: str | None = None,
) -> AgentInfo | None:
    """Get information on the agent or None if not found."""
    agent = async_get_agent(hass, agent_id)

    if agent is None:
        return None

    if isinstance(agent, ConversationEntity):
        name = agent.name
        if not isinstance(name, str):
            name = agent.entity_id
        return AgentInfo(
            id=agent.entity_id,
            name=name,
            supports_streaming=agent.supports_streaming,
        )

    manager = get_agent_manager(hass)

    for agent_info in manager.async_get_agent_info():
        if agent_info.id == agent_id:
            return agent_info

    return None


async def async_prepare_agent(
    hass: HomeAssistant, agent_id: str | None, language: str
) -> None:
    """Prepare given agent."""
    agent = async_get_agent(hass, agent_id)

    if agent is None:
        raise ValueError("Invalid agent specified")

    await agent.async_prepare(language)


async def async_handle_sentence_triggers(
    hass: HomeAssistant,
    user_input: ConversationInput,
    chat_log: ChatLog,
) -> str | None:
    """Try to match input against sentence triggers and return response text.

    Returns None if no match occurred.
    """
    agent = get_agent_manager(hass).default_agent
    assert agent is not None

    return await agent.async_handle_sentence_triggers(user_input, chat_log)


async def async_handle_intents(
    hass: HomeAssistant,
    user_input: ConversationInput,
    chat_log: ChatLog,
    *,
    intent_filter: Callable[[RecognizeResult], bool] | None = None,
) -> intent.IntentResponse | None:
    """Try to match input against registered intents and return response.

    Returns None if no match occurred.
    """
    agent = get_agent_manager(hass).default_agent
    assert agent is not None

    return await agent.async_handle_intents(
        user_input, chat_log, intent_filter=intent_filter
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[ConversationEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component

    manager = get_agent_manager(hass)

    hass_config_path = hass.config.path()
    config_intents = _get_config_intents(config, hass_config_path)
    manager.update_config_intents(config_intents)

    await async_setup_default_agent(hass, entity_component)

    async def handle_process(service: ServiceCall) -> ServiceResponse:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        try:
            result = await async_converse(
                hass=hass,
                text=text,
                conversation_id=service.data.get(ATTR_CONVERSATION_ID),
                context=service.context,
                language=service.data.get(ATTR_LANGUAGE),
                agent_id=service.data.get(ATTR_AGENT_ID),
            )
        except intent.IntentHandleError as err:
            raise HomeAssistantError(f"Error processing {text}: {err}") from err

        if service.return_response:
            return result.as_dict()

        return None

    async def handle_reload(service: ServiceCall) -> None:
        """Reload intents."""
        language = service.data.get(ATTR_LANGUAGE)
        if language is None:
            conf = await async_integration_yaml_config(hass, DOMAIN)
            if conf is not None:
                config_intents = _get_config_intents(conf, hass_config_path)
                manager.update_config_intents(config_intents)

        agent = manager.default_agent
        if agent is not None:
            await agent.async_reload(language=language)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS,
        handle_process,
        schema=SERVICE_PROCESS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, handle_reload, schema=SERVICE_RELOAD_SCHEMA
    )
    async_setup_conversation_http(hass)

    return True


def _get_config_intents(config: ConfigType, hass_config_path: str) -> dict[str, Any]:
    """Return config intents."""
    intents = config.get(DOMAIN, {}).get("intents", {})
    return {
        "intents": {
            intent_name: {
                "data": [
                    {
                        "sentences": sentences,
                        "metadata": {
                            METADATA_CUSTOM_SENTENCE: True,
                            METADATA_CUSTOM_FILE: hass_config_path,
                        },
                    }
                ]
            }
            for intent_name, sentences in intents.items()
        }
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
