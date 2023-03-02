"""Support for functionality to have conversations with Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent, singleton
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .default_agent import DefaultAgent

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
    return AgentManager(hass)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    agent_manager = _get_agent_manager(hass)

    if config_intents := config.get(DOMAIN, {}).get("intents"):
        hass.data[DATA_CONFIG] = config_intents

    async def handle_process(service: core.ServiceCall) -> None:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        try:
            await async_converse(
                hass=hass,
                text=text,
                conversation_id=None,
                context=service.context,
                language=service.data.get(ATTR_LANGUAGE),
                agent_id=service.data.get(ATTR_AGENT_ID),
            )
        except intent.IntentHandleError as err:
            _LOGGER.error("Error processing %s: %s", text, err)

    async def handle_reload(service: core.ServiceCall) -> None:
        """Reload intents."""
        agent = await agent_manager.async_get_agent()
        await agent.async_reload(language=service.data.get(ATTR_LANGUAGE))

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, handle_process, schema=SERVICE_PROCESS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, handle_reload, schema=SERVICE_RELOAD_SCHEMA
    )
    hass.http.register_view(ConversationProcessView())
    websocket_api.async_register_command(hass, websocket_process)
    websocket_api.async_register_command(hass, websocket_prepare)
    websocket_api.async_register_command(hass, websocket_get_agent_info)
    websocket_api.async_register_command(hass, websocket_list_agents)

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
        vol.Required("type"): "conversation/agent/info",
        vol.Optional("agent_id"): agent_id_validator,
    }
)
@websocket_api.async_response
async def websocket_get_agent_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Info about the agent in use."""
    agent = await _get_agent_manager(hass).async_get_agent(msg.get("agent_id"))

    connection.send_result(
        msg["id"],
        {
            "attribution": agent.attribution,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/agent/list",
    }
)
@core.callback
def websocket_list_agents(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List available agents."""
    manager = _get_agent_manager(hass)

    connection.send_result(
        msg["id"],
        {
            "default_agent": manager.default_agent,
            "agents": manager.async_get_agent_info(),
        },
    )


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


async def async_converse(
    hass: core.HomeAssistant,
    text: str,
    conversation_id: str | None,
    context: core.Context,
    language: str | None = None,
    agent_id: str | None = None,
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
            language=language,
        )
    )
    return result


class AgentManager:
    """Class to manage conversation agents."""

    HOME_ASSISTANT_AGENT = "homeassistant"

    default_agent: str = HOME_ASSISTANT_AGENT
    _builtin_agent: AbstractConversationAgent | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the conversation agents."""
        self.hass = hass
        self._agents: dict[str, AbstractConversationAgent] = {}
        self._default_agent_init_lock = asyncio.Lock()

    async def async_get_agent(
        self, agent_id: str | None = None
    ) -> AbstractConversationAgent:
        """Get the agent."""
        if agent_id is None:
            agent_id = self.default_agent

        if agent_id == AgentManager.HOME_ASSISTANT_AGENT:
            if self._builtin_agent is not None:
                return self._builtin_agent

            async with self._default_agent_init_lock:
                if self._builtin_agent is not None:
                    return self._builtin_agent

                self._builtin_agent = DefaultAgent(self.hass)
                await self._builtin_agent.async_initialize(
                    self.hass.data.get(DATA_CONFIG)
                )

            return self._builtin_agent

        return self._agents[agent_id]

    @core.callback
    def async_get_agent_info(self) -> list[dict[str, Any]]:
        """List all agents."""
        agents = [
            {
                "id": AgentManager.HOME_ASSISTANT_AGENT,
                "name": "Home Assistant",
            }
        ]
        for agent_id, agent in self._agents.items():
            config_entry = self.hass.config_entries.async_get_entry(agent_id)

            # This is a bug, agent should have been unset when config entry was unloaded
            if config_entry is None:
                _LOGGER.warning(
                    "Agent was still loaded while config entry is gone: %s", agent
                )
                continue

            agents.append(
                {
                    "id": agent_id,
                    "name": config_entry.title,
                }
            )
        return agents

    @core.callback
    def async_is_valid_agent_id(self, agent_id: str) -> bool:
        """Check if the agent id is valid."""
        return agent_id in self._agents or agent_id == AgentManager.HOME_ASSISTANT_AGENT

    @core.callback
    def async_set_agent(self, agent_id: str, agent: AbstractConversationAgent) -> None:
        """Set the agent."""
        self._agents[agent_id] = agent
        if self.default_agent == AgentManager.HOME_ASSISTANT_AGENT:
            self.default_agent = agent_id

    @core.callback
    def async_unset_agent(self, agent_id: str) -> None:
        """Unset the agent."""
        if self.default_agent == agent_id:
            self.default_agent = AgentManager.HOME_ASSISTANT_AGENT
        self._agents.pop(agent_id, None)
