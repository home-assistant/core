"""Agent foundation for conversation integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, async_get_hass, callback
from homeassistant.helpers import config_validation as cv, singleton

from .const import (
    DATA_COMPONENT,
    DATA_DEFAULT_ENTITY,
    HOME_ASSISTANT_AGENT,
    OLD_HOME_ASSISTANT_AGENT,
)
from .entity import ConversationEntity
from .models import (
    AbstractConversationAgent,
    AgentInfo,
    ConversationInput,
    ConversationResult,
)
from .trace import (
    ConversationTraceEvent,
    ConversationTraceEventType,
    async_conversation_trace,
)

_LOGGER = logging.getLogger(__name__)


@singleton.singleton("conversation_agent")
@callback
def get_agent_manager(hass: HomeAssistant) -> AgentManager:
    """Get the active agent."""
    return AgentManager(hass)


def agent_id_validator(value: Any) -> str:
    """Validate agent ID."""
    hass = async_get_hass()
    if async_get_agent(hass, cv.string(value)) is None:
        raise vol.Invalid("invalid agent ID")
    return value


@callback
def async_get_agent(
    hass: HomeAssistant, agent_id: str | None = None
) -> AbstractConversationAgent | ConversationEntity | None:
    """Get specified agent."""
    if agent_id is None or agent_id in (HOME_ASSISTANT_AGENT, OLD_HOME_ASSISTANT_AGENT):
        return hass.data[DATA_DEFAULT_ENTITY]

    if "." in agent_id:
        return hass.data[DATA_COMPONENT].get_entity(agent_id)

    manager = get_agent_manager(hass)

    if not manager.async_is_valid_agent_id(agent_id):
        return None

    return manager.async_get_agent(agent_id)


async def async_converse(
    hass: HomeAssistant,
    text: str,
    conversation_id: str | None,
    context: Context,
    language: str | None = None,
    agent_id: str | None = None,
    device_id: str | None = None,
    extra_system_prompt: str | None = None,
) -> ConversationResult:
    """Process text and get intent."""
    agent = async_get_agent(hass, agent_id)

    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")

    if isinstance(agent, ConversationEntity):
        agent.async_set_context(context)
        method = agent.internal_async_process
    else:
        method = agent.async_process

    if language is None:
        language = hass.config.language

    _LOGGER.debug("Processing in %s: %s", language, text)
    conversation_input = ConversationInput(
        text=text,
        context=context,
        conversation_id=conversation_id,
        device_id=device_id,
        language=language,
        agent_id=agent_id,
        extra_system_prompt=extra_system_prompt,
    )
    with async_conversation_trace() as trace:
        trace.add_event(
            ConversationTraceEvent(
                ConversationTraceEventType.ASYNC_PROCESS,
                dataclasses.asdict(conversation_input),
            )
        )
        result = await method(conversation_input)
        trace.set_result(**result.as_dict())
        return result


class AgentManager:
    """Class to manage conversation agents."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the conversation agents."""
        self.hass = hass
        self._agents: dict[str, AbstractConversationAgent] = {}

    @callback
    def async_get_agent(self, agent_id: str) -> AbstractConversationAgent | None:
        """Get the agent."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        return self._agents[agent_id]

    @callback
    def async_get_agent_info(self) -> list[AgentInfo]:
        """List all agents."""
        agents: list[AgentInfo] = []
        for agent_id, agent in self._agents.items():
            config_entry = self.hass.config_entries.async_get_entry(agent_id)

            # Guard against potential bugs in conversation agents where the agent is not
            # removed from the manager when the config entry is removed
            if config_entry is None:
                _LOGGER.warning(
                    "Conversation agent %s is still loaded after config entry removal",
                    agent,
                )
                continue

            agents.append(
                AgentInfo(
                    id=agent_id,
                    name=config_entry.title or config_entry.domain,
                )
            )
        return agents

    @callback
    def async_is_valid_agent_id(self, agent_id: str) -> bool:
        """Check if the agent id is valid."""
        return agent_id in self._agents

    @callback
    def async_set_agent(self, agent_id: str, agent: AbstractConversationAgent) -> None:
        """Set the agent."""
        self._agents[agent_id] = agent

    @callback
    def async_unset_agent(self, agent_id: str) -> None:
        """Unset the agent."""
        self._agents.pop(agent_id, None)
