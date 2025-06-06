"""Support for functionality to have conversations with Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Literal

from hassil.recognize import RecognizeResult
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent_manager import AgentInfo, async_converse, async_get_agent, get_agent_manager
from .chat_log import (
    AssistantContent,
    AssistantContentDeltaDict,
    ChatLog,
    Content,
    ConverseError,
    SystemContent,
    ToolResultContent,
    UserContent,
    async_get_chat_log,
)
from .const import (
    DATA_COMPONENT,
    DOMAIN,
    HOME_ASSISTANT_AGENT,
    OLD_HOME_ASSISTANT_AGENT,
    ConversationEntityFeature,
)
from .default_agent import DefaultAgent, async_setup_default_agent
from .entity import ConversationEntity
from .http import async_setup as async_setup_conversation_http
from .models import AbstractConversationAgent, ConversationInput, ConversationResult
from .services import async_setup_services
from .trace import ConversationTraceEventType, async_conversation_trace_append

__all__ = [
    "DOMAIN",
    "HOME_ASSISTANT_AGENT",
    "OLD_HOME_ASSISTANT_AGENT",
    "AssistantContent",
    "AssistantContentDeltaDict",
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
    "UserContent",
    "async_conversation_trace_append",
    "async_converse",
    "async_get_agent_info",
    "async_get_chat_log",
    "async_set_agent",
    "async_setup",
    "async_unset_agent",
]

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional("intents"): vol.Schema(
                    {cv.string: vol.All(cv.ensure_list, [cv.string])}
                )
            }
        )
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
    """Set the agent to handle the conversations."""
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
    hass: HomeAssistant, user_input: ConversationInput
) -> str | None:
    """Try to match input against sentence triggers and return response text.

    Returns None if no match occurred.
    """
    default_agent = async_get_agent(hass)
    assert isinstance(default_agent, DefaultAgent)

    return await default_agent.async_handle_sentence_triggers(user_input)


async def async_handle_intents(
    hass: HomeAssistant,
    user_input: ConversationInput,
    *,
    intent_filter: Callable[[RecognizeResult], bool] | None = None,
) -> intent.IntentResponse | None:
    """Try to match input against registered intents and return response.

    Returns None if no match occurred.
    """
    default_agent = async_get_agent(hass)
    assert isinstance(default_agent, DefaultAgent)

    return await default_agent.async_handle_intents(
        user_input, intent_filter=intent_filter
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[ConversationEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component

    await async_setup_default_agent(
        hass, entity_component, config.get(DOMAIN, {}).get("intents", {})
    )

    # Temporary migration. We can remove this in 2024.10
    from homeassistant.components.assist_pipeline import (  # pylint: disable=import-outside-toplevel
        async_migrate_engine,
    )

    async_migrate_engine(
        hass, "conversation", OLD_HOME_ASSISTANT_AGENT, HOME_ASSISTANT_AGENT
    )

    async_setup_services(hass)

    async_setup_conversation_http(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
