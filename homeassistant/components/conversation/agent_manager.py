"""Agent foundation for conversation integration."""

from __future__ import annotations

from collections.abc import Callable
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

from .const import DATA_COMPONENT, HOME_ASSISTANT_AGENT, IntentSource
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

TRIGGER_INTENT_NAME_PREFIX = "HassSentenceTrigger"

if TYPE_CHECKING:
    from .default_agent import DefaultAgent
    from .trigger import TRIGGER_CALLBACK_TYPE


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


type IntentSourceConfig = dict[str, dict[str, Any]]
type IntentsCallback = Callable[[dict[IntentSource, IntentSourceConfig]], None]


class AgentManager:
    """Class to manage conversation agents."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the conversation agents."""
        self.hass = hass
        self._agents: dict[str, AbstractConversationAgent] = {}
        self.default_agent: DefaultAgent | None = None
        self._intents: dict[IntentSource, IntentSourceConfig] = {
            IntentSource.CONFIG: {"intents": {}},
            IntentSource.TRIGGER: {"intents": {}},
        }
        self._intents_subscribers: list[IntentsCallback] = []
        self._trigger_callbacks: dict[int, TRIGGER_CALLBACK_TYPE] = {}
        self._trigger_callback_counter: int = 0

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
        self.default_agent = agent

    @callback
    def subscribe_intents(self, subscriber: IntentsCallback) -> CALLBACK_TYPE:
        """Subscribe to intents updates.

        The subscriber callback is called immediately with all intent sources
        and whenever intents are updated (only with the changed source).
        """
        subscriber(self._intents)
        self._intents_subscribers.append(subscriber)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe from intents updates."""
            self._intents_subscribers.remove(subscriber)

        return unsubscribe

    def _notify_intents_subscribers(self, source: IntentSource) -> None:
        """Notify all intents subscribers of a change to a specific source."""
        update = {source: self._intents[source]}
        for subscriber in self._intents_subscribers:
            subscriber(update)

    def update_config_intents(self, intents: dict[str, Any]) -> None:
        """Update config intents."""
        self._intents[IntentSource.CONFIG]["intents"] = intents
        self._notify_intents_subscribers(IntentSource.CONFIG)

    def register_trigger(
        self, sentences: list[str], trigger_callback: TRIGGER_CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Register a trigger."""
        trigger_id = self._trigger_callback_counter
        self._trigger_callback_counter += 1
        trigger_intent_name = f"{TRIGGER_INTENT_NAME_PREFIX}{trigger_id}"

        trigger_intents = self._intents[IntentSource.TRIGGER]
        trigger_intents["intents"][trigger_intent_name] = {
            "data": [{"sentences": sentences}]
        }
        self._trigger_callbacks[trigger_id] = trigger_callback
        self._notify_intents_subscribers(IntentSource.TRIGGER)

        @callback
        def unregister_trigger() -> None:
            """Unregister the trigger."""
            del trigger_intents["intents"][trigger_intent_name]
            del self._trigger_callbacks[trigger_id]
            self._notify_intents_subscribers(IntentSource.TRIGGER)

        return unregister_trigger

    @property
    def trigger_sentences(self) -> list[str]:
        """Get all trigger sentences."""
        sentences: list[str] = []
        trigger_intents = self._intents[IntentSource.TRIGGER]
        for trigger_intent in trigger_intents.get("intents", {}).values():
            for data in trigger_intent.get("data", []):
                sentences.extend(data.get("sentences", []))
        return sentences

    def get_trigger_callback(
        self, trigger_intent_name: str
    ) -> TRIGGER_CALLBACK_TYPE | None:
        """Get the callback for a trigger from its intent name."""
        if not trigger_intent_name.startswith(TRIGGER_INTENT_NAME_PREFIX):
            return None
        trigger_id = int(trigger_intent_name[len(TRIGGER_INTENT_NAME_PREFIX) :])
        return self._trigger_callbacks.get(trigger_id)
