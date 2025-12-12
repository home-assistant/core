"""Agent foundation for conversation integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HomeAssistant,
    async_get_hass,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent, singleton

from .const import DATA_COMPONENT, HOME_ASSISTANT_AGENT
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

if TYPE_CHECKING:
    from .default_agent import DefaultAgent
    from .trigger import TriggerDetails


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
    manager = get_agent_manager(hass)

    if agent_id is None or agent_id == HOME_ASSISTANT_AGENT:
        return manager.default_agent

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
    satellite_id: str | None = None,
    extra_system_prompt: str | None = None,
) -> ConversationResult:
    """Process text and get intent."""
    if agent_id is None:
        agent_id = HOME_ASSISTANT_AGENT

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
        satellite_id=satellite_id,
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
        try:
            result = await method(conversation_input)
        except HomeAssistantError as err:
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                str(err),
            )
            result = ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )

        trace.set_result(**result.as_dict())
        return result


class AgentManager:
    """Class to manage conversation agents."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the conversation agents."""
        self.hass = hass
        self._agents: dict[str, AbstractConversationAgent] = {}
        self.default_agent: DefaultAgent | None = None
        self.config_intents: dict[str, Any] = {}
        self.triggers_details: list[TriggerDetails] = []

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
                    supports_streaming=False,
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

    async def async_setup_default_agent(self, agent: DefaultAgent) -> None:
        """Set up the default agent."""
        agent.update_config_intents(self.config_intents)
        agent.update_triggers(self.triggers_details)
        self.default_agent = agent

    def update_config_intents(self, intents: dict[str, Any]) -> None:
        """Update config intents."""
        self.config_intents = intents
        if self.default_agent is not None:
            self.default_agent.update_config_intents(intents)

    def register_trigger(self, trigger_details: TriggerDetails) -> CALLBACK_TYPE:
        """Register a trigger."""
        self.triggers_details.append(trigger_details)
        if self.default_agent is not None:
            self.default_agent.update_triggers(self.triggers_details)

        @callback
        def unregister_trigger() -> None:
            """Unregister the trigger."""
            self.triggers_details.remove(trigger_details)
            if self.default_agent is not None:
                self.default_agent.update_triggers(self.triggers_details)

        return unregister_trigger
