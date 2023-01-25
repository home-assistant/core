"""Support for functionality to have conversations with Home Assistant."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .default_agent import DefaultAgent

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = "text"
ATTR_LANGUAGE = "language"

DOMAIN = "conversation"

REGEX_TYPE = type(re.compile(""))
DATA_AGENT = "conversation_agent"
DATA_CONFIG = "conversation_config"

SERVICE_PROCESS = "process"
SERVICE_RELOAD = "reload"

SERVICE_PROCESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_LANGUAGE): cv.string,
    }
)


SERVICE_RELOAD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_LANGUAGE): cv.string,
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


@core.callback
@bind_hass
def async_set_agent(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    agent: AbstractConversationAgent,
):
    """Set the agent to handle the conversations."""
    hass.data[DATA_AGENT] = agent


@core.callback
@bind_hass
def async_unset_agent(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
):
    """Set the agent to handle the conversations."""
    hass.data[DATA_AGENT] = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    if config_intents := config.get(DOMAIN, {}).get("intents"):
        hass.data[DATA_CONFIG] = config_intents

    async def handle_process(service: core.ServiceCall) -> None:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        agent = await _get_agent(hass)
        try:
            await agent.async_process(
                ConversationInput(
                    text=text,
                    context=service.context,
                    conversation_id=None,
                    language=service.data.get(ATTR_LANGUAGE, hass.config.language),
                )
            )
        except intent.IntentHandleError as err:
            _LOGGER.error("Error processing %s: %s", text, err)

    async def handle_reload(service: core.ServiceCall) -> None:
        """Reload intents."""
        agent = await _get_agent(hass)
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

    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/process",
        vol.Required("text"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
        vol.Optional("language"): str,
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
        hass,
        msg["text"],
        msg.get("conversation_id"),
        connection.context(msg),
        msg.get("language"),
    )
    connection.send_result(msg["id"], result.as_dict())


@websocket_api.websocket_command(
    {
        "type": "conversation/prepare",
        vol.Optional("language"): str,
    }
)
@websocket_api.async_response
async def websocket_prepare(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Reload intents."""
    agent = await _get_agent(hass)
    await agent.async_prepare(msg.get("language"))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/agent/info",
    }
)
@websocket_api.async_response
async def websocket_get_agent_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Info about the agent in use."""
    agent = await _get_agent(hass)

    connection.send_result(
        msg["id"],
        {
            "attribution": agent.attribution,
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
        )

        return self.json(result.as_dict())


async def _get_agent(hass: core.HomeAssistant) -> AbstractConversationAgent:
    """Get the active conversation agent."""
    if (agent := hass.data.get(DATA_AGENT)) is None:
        agent = hass.data[DATA_AGENT] = DefaultAgent(hass)
        await agent.async_initialize(hass.data.get(DATA_CONFIG))
    return agent


async def async_converse(
    hass: core.HomeAssistant,
    text: str,
    conversation_id: str | None,
    context: core.Context,
    language: str | None = None,
) -> ConversationResult:
    """Process text and get intent."""
    agent = await _get_agent(hass)
    if language is None:
        language = hass.config.language

    result = await agent.async_process(
        ConversationInput(
            text=text,
            context=context,
            conversation_id=conversation_id,
            language=language,
        )
    )
    return result
