"""Agent foundation for conversation integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, async_get_hass, callback
from homeassistant.helpers import config_validation as cv, singleton

from .const import DATA_CONFIG, HOME_ASSISTANT_AGENT
from .default_agent import DefaultAgent, async_setup as async_setup_default_agent
from .models import AbstractConversationAgent, ConversationInput, ConversationResult

_LOGGER = logging.getLogger(__name__)


@singleton.singleton("conversation_agent")
@callback
def get_agent_manager(hass: HomeAssistant) -> AgentManager:
    """Get the active agent."""
    manager = AgentManager(hass)
    manager.async_setup()
    return manager


def agent_id_validator(value: Any) -> str:
    """Validate agent ID."""
    hass = async_get_hass()
    manager = get_agent_manager(hass)
    if not manager.async_is_valid_agent_id(cv.string(value)):
        raise vol.Invalid("invalid agent ID")
    return value


async def async_converse(
    hass: HomeAssistant,
    text: str,
    conversation_id: str | None,
    context: Context,
    language: str | None = None,
    agent_id: str | None = None,
    device_id: str | None = None,
) -> ConversationResult:
    """Process text and get intent."""
    agent = await get_agent_manager(hass).async_get_agent(agent_id)

    if language is None:
        language = hass.config.language

    _LOGGER.debug("Processing in %s: %s", language, text)
    result = await agent.async_process(
        ConversationInput(
            text=text,
            context=context,
            conversation_id=conversation_id,
            device_id=device_id,
            language=language,
        )
    )
    return result


@dataclass(frozen=True)
class AgentInfo:
    """Container for conversation agent info."""

    id: str
    name: str


class AgentManager:
    """Class to manage conversation agents."""

    default_agent: str = HOME_ASSISTANT_AGENT
    _builtin_agent: AbstractConversationAgent | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the conversation agents."""
        self.hass = hass
        self._agents: dict[str, AbstractConversationAgent] = {}
        self._builtin_agent_init_lock = asyncio.Lock()

    def async_setup(self) -> None:
        """Set up the conversation agents."""
        async_setup_default_agent(self.hass)

    async def async_get_agent(
        self, agent_id: str | None = None
    ) -> AbstractConversationAgent:
        """Get the agent."""
        if agent_id is None:
            agent_id = self.default_agent

        if agent_id == HOME_ASSISTANT_AGENT:
            if self._builtin_agent is not None:
                return self._builtin_agent

            async with self._builtin_agent_init_lock:
                if self._builtin_agent is not None:
                    return self._builtin_agent

                self._builtin_agent = DefaultAgent(self.hass)
                await self._builtin_agent.async_initialize(
                    self.hass.data.get(DATA_CONFIG)
                )

            return self._builtin_agent

        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        return self._agents[agent_id]

    @callback
    def async_get_agent_info(self) -> list[AgentInfo]:
        """List all agents."""
        agents: list[AgentInfo] = [
            AgentInfo(
                id=HOME_ASSISTANT_AGENT,
                name="Home Assistant",
            )
        ]
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
        return agent_id in self._agents or agent_id == HOME_ASSISTANT_AGENT

    @callback
    def async_set_agent(self, agent_id: str, agent: AbstractConversationAgent) -> None:
        """Set the agent."""
        self._agents[agent_id] = agent

    @callback
    def async_unset_agent(self, agent_id: str) -> None:
        """Unset the agent."""
        self._agents.pop(agent_id, None)
