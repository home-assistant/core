"""Support for functionality to have conversations with Home Assistant."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
import logging
import re
from typing import Any, Literal

from hassil.recognize import RecognizeResult
import voluptuous as vol

from homeassistant import core
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent, singleton
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import language as language_util

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .const import HOME_ASSISTANT_AGENT
from .default_agent import DefaultAgent, async_setup as async_setup_default_agent

__all__ = [
    "DOMAIN",
    "HOME_ASSISTANT_AGENT",
    "async_converse",
    "async_get_agent_info",
    "async_set_agent",
    "async_unset_agent",
    "async_setup",
]

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = "text"
ATTR_LANGUAGE = "language"
ATTR_AGENT_ID = "agent_id"

DOMAIN = "conversation"

REGEX_TYPE = type(re.compile(""))
DATA_CONFIG = "conversation_config"

SERVICE_PROCESS = "process"
SERVICE_RELOAD = "reload"


def agent_id_validator(value: Any) -> str:
    """Validate agent ID."""
    hass = core.async_get_hass()
    manager = _get_agent_manager(hass)
    if not manager.async_is_valid_agent_id(cv.string(value)):
        raise vol.Invalid("invalid agent ID")
    return value


SERVICE_PROCESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_AGENT_ID): agent_id_validator,
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
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@singleton.singleton("conversation_agent")
@core.callback
def _get_agent_manager(hass: HomeAssistant) -> AgentManager:
    """Get the active agent."""
    manager = AgentManager(hass)
    manager.async_setup()
    return manager


@core.callback
@bind_hass
def async_set_agent(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    agent: AbstractConversationAgent,
):
    """Set the agent to handle the conversations."""
    _get_agent_manager(hass).async_set_agent(config_entry.entry_id, agent)


@core.callback
@bind_hass
def async_unset_agent(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
):
    """Set the agent to handle the conversations."""
    _get_agent_manager(hass).async_unset_agent(config_entry.entry_id)


async def async_get_conversation_languages(
    hass: HomeAssistant, agent_id: str | None = None
) -> set[str] | Literal["*"]:
    """Return languages supported by conversation agents.

    If an agent is specified, returns a set of languages supported by that agent.
    If no agent is specified, return a set with the union of languages supported by
    all conversation agents.
    """
    agent_manager = _get_agent_manager(hass)
    languages = set()

    agent_ids: Iterable[str]
    if agent_id is None:
        agent_ids = iter(info.id for info in agent_manager.async_get_agent_info())
    else:
        agent_ids = (agent_id,)

    for _agent_id in agent_ids:
        agent = await agent_manager.async_get_agent(_agent_id)
        if agent.supported_languages == MATCH_ALL:
            return MATCH_ALL
        for language_tag in agent.supported_languages:
            languages.add(language_tag)

    return languages


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    agent_manager = _get_agent_manager(hass)

    if config_intents := config.get(DOMAIN, {}).get("intents"):
        hass.data[DATA_CONFIG] = config_intents

    async def handle_process(service: core.ServiceCall) -> core.ServiceResponse:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        try:
            result = await async_converse(
                hass=hass,
                text=text,
                conversation_id=None,
                context=service.context,
                language=service.data.get(ATTR_LANGUAGE),
                agent_id=service.data.get(ATTR_AGENT_ID),
            )
        except intent.IntentHandleError as err:
            raise HomeAssistantError(f"Error processing {text}: {err}") from err

        if service.return_response:
            return result.as_dict()

        return None

    async def handle_reload(service: core.ServiceCall) -> None:
        """Reload intents."""
        agent = await agent_manager.async_get_agent()
        await agent.async_reload(language=service.data.get(ATTR_LANGUAGE))

    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS,
        handle_process,
        schema=SERVICE_PROCESS_SCHEMA,
        supports_response=core.SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, handle_reload, schema=SERVICE_RELOAD_SCHEMA
    )
    hass.http.register_view(ConversationProcessView())
    websocket_api.async_register_command(hass, websocket_process)
    websocket_api.async_register_command(hass, websocket_prepare)
    websocket_api.async_register_command(hass, websocket_list_agents)
    websocket_api.async_register_command(hass, websocket_hass_agent_debug)

    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/process",
        vol.Required("text"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
        vol.Optional("language"): str,
        vol.Optional("agent_id"): agent_id_validator,
    }
)
@websocket_api.async_response
async def websocket_process(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Process text."""
    result = await async_converse(
        hass=hass,
        text=msg["text"],
        conversation_id=msg.get("conversation_id"),
        context=connection.context(msg),
        language=msg.get("language"),
        agent_id=msg.get("agent_id"),
    )
    connection.send_result(msg["id"], result.as_dict())


@websocket_api.websocket_command(
    {
        "type": "conversation/prepare",
        vol.Optional("language"): str,
        vol.Optional("agent_id"): agent_id_validator,
    }
)
@websocket_api.async_response
async def websocket_prepare(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Reload intents."""
    manager = _get_agent_manager(hass)
    agent = await manager.async_get_agent(msg.get("agent_id"))
    await agent.async_prepare(msg.get("language"))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/agent/list",
        vol.Optional("language"): str,
        vol.Optional("country"): str,
    }
)
@websocket_api.async_response
async def websocket_list_agents(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List conversation agents and, optionally, if they support a given language."""
    manager = _get_agent_manager(hass)

    country = msg.get("country")
    language = msg.get("language")
    agents = []

    for agent_info in manager.async_get_agent_info():
        agent = await manager.async_get_agent(agent_info.id)

        supported_languages = agent.supported_languages
        if language and supported_languages != MATCH_ALL:
            supported_languages = language_util.matches(
                language, supported_languages, country
            )

        agent_dict: dict[str, Any] = {
            "id": agent_info.id,
            "name": agent_info.name,
            "supported_languages": supported_languages,
        }
        agents.append(agent_dict)

    connection.send_message(websocket_api.result_message(msg["id"], {"agents": agents}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/agent/homeassistant/debug",
        vol.Required("sentences"): [str],
        vol.Optional("language"): str,
        vol.Optional("device_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def websocket_hass_agent_debug(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return intents that would be matched by the default agent for a list of sentences."""
    agent = await _get_agent_manager(hass).async_get_agent(HOME_ASSISTANT_AGENT)
    assert isinstance(agent, DefaultAgent)
    results = [
        await agent.async_recognize(
            ConversationInput(
                text=sentence,
                context=connection.context(msg),
                conversation_id=None,
                device_id=msg.get("device_id"),
                language=msg.get("language", hass.config.language),
            )
        )
        for sentence in msg["sentences"]
    ]

    # Return results for each sentence in the same order as the input.
    connection.send_result(
        msg["id"],
        {
            "results": [
                {
                    "intent": {
                        "name": result.intent.name,
                    },
                    "slots": {  # direct access to values
                        entity_key: entity.value
                        for entity_key, entity in result.entities.items()
                    },
                    "details": {
                        entity_key: {
                            "name": entity.name,
                            "value": entity.value,
                            "text": entity.text,
                        }
                        for entity_key, entity in result.entities.items()
                    },
                    "targets": {
                        state.entity_id: {"matched": is_matched}
                        for state, is_matched in _get_debug_targets(hass, result)
                    },
                }
                if result is not None
                else None
                for result in results
            ]
        },
    )


def _get_debug_targets(
    hass: HomeAssistant,
    result: RecognizeResult,
) -> Iterable[tuple[core.State, bool]]:
    """Yield state/is_matched pairs for a hassil recognition."""
    entities = result.entities

    name: str | None = None
    area_name: str | None = None
    domains: set[str] | None = None
    device_classes: set[str] | None = None
    state_names: set[str] | None = None

    if "name" in entities:
        name = str(entities["name"].value)

    if "area" in entities:
        area_name = str(entities["area"].value)

    if "domain" in entities:
        domains = set(cv.ensure_list(entities["domain"].value))

    if "device_class" in entities:
        device_classes = set(cv.ensure_list(entities["device_class"].value))

    if "state" in entities:
        # HassGetState only
        state_names = set(cv.ensure_list(entities["state"].value))

    states = intent.async_match_states(
        hass,
        name=name,
        area_name=area_name,
        domains=domains,
        device_classes=device_classes,
    )

    for state in states:
        # For queries, a target is "matched" based on its state
        is_matched = (state_names is None) or (state.state in state_names)
        yield state, is_matched


class ConversationProcessView(http.HomeAssistantView):
    """View to process text."""

    url = "/api/conversation/process"
    name = "api:conversation:process"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("text"): str,
                vol.Optional("conversation_id"): str,
                vol.Optional("language"): str,
                vol.Optional("agent_id"): agent_id_validator,
            }
        )
    )
    async def post(self, request, data):
        """Send a request for processing."""
        hass = request.app["hass"]

        result = await async_converse(
            hass,
            text=data["text"],
            conversation_id=data.get("conversation_id"),
            context=self.context(request),
            language=data.get("language"),
            agent_id=data.get("agent_id"),
        )

        return self.json(result.as_dict())


@dataclass(frozen=True)
class AgentInfo:
    """Container for conversation agent info."""

    id: str
    name: str


@core.callback
def async_get_agent_info(
    hass: core.HomeAssistant,
    agent_id: str | None = None,
) -> AgentInfo | None:
    """Get information on the agent or None if not found."""
    manager = _get_agent_manager(hass)

    if agent_id is None:
        agent_id = manager.default_agent

    for agent_info in manager.async_get_agent_info():
        if agent_info.id == agent_id:
            return agent_info

    return None


async def async_converse(
    hass: core.HomeAssistant,
    text: str,
    conversation_id: str | None,
    context: core.Context,
    language: str | None = None,
    agent_id: str | None = None,
    device_id: str | None = None,
) -> ConversationResult:
    """Process text and get intent."""
    agent = await _get_agent_manager(hass).async_get_agent(agent_id)

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

    @core.callback
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

    @core.callback
    def async_is_valid_agent_id(self, agent_id: str) -> bool:
        """Check if the agent id is valid."""
        return agent_id in self._agents or agent_id == HOME_ASSISTANT_AGENT

    @core.callback
    def async_set_agent(self, agent_id: str, agent: AbstractConversationAgent) -> None:
        """Set the agent."""
        self._agents[agent_id] = agent

    @core.callback
    def async_unset_agent(self, agent_id: str) -> None:
        """Unset the agent."""
        self._agents.pop(agent_id, None)
