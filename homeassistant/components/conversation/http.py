"""HTTP endpoints for conversation integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import language as language_util

from .agent_manager import (
    agent_id_validator,
    async_converse,
    async_get_agent,
    get_agent_manager,
)
from .const import DATA_COMPONENT
from .entity import ConversationEntity
from .models import ConversationInput


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    hass.http.register_view(ConversationProcessView())
    websocket_api.async_register_command(hass, websocket_process)
    websocket_api.async_register_command(hass, websocket_prepare)
    websocket_api.async_register_command(hass, websocket_list_agents)
    websocket_api.async_register_command(hass, websocket_list_sentences)
    websocket_api.async_register_command(hass, websocket_hass_agent_debug)
    websocket_api.async_register_command(hass, websocket_hass_agent_language_scores)


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
    agent = async_get_agent(hass, msg.get("agent_id"))

    if agent is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Agent not found")
        return

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
    country = msg.get("country")
    language = msg.get("language")
    agents = []

    for entity in hass.data[DATA_COMPONENT].entities:
        supported_languages = entity.supported_languages
        if language and supported_languages != MATCH_ALL:
            supported_languages = language_util.matches(
                language, supported_languages, country
            )

        name = entity.entity_id
        if state := hass.states.get(entity.entity_id):
            name = state.name

        agents.append(
            {
                "id": entity.entity_id,
                "name": name,
                "supported_languages": supported_languages,
            }
        )

    manager = get_agent_manager(hass)

    for agent_info in manager.async_get_agent_info():
        agent = manager.async_get_agent(agent_info.id)
        assert agent is not None

        if isinstance(agent, ConversationEntity):
            continue

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
        vol.Required("type"): "conversation/sentences/list",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_list_sentences(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List custom registered sentences."""
    manager = get_agent_manager(hass)

    sentences = []
    for trigger_details in manager.triggers_details:
        sentences.extend(trigger_details.sentences)

    connection.send_result(msg["id"], {"trigger_sentences": sentences})


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
    agent = get_agent_manager(hass).default_agent
    assert agent is not None

    # Return results for each sentence in the same order as the input.
    result_dicts: list[dict[str, Any] | None] = []
    for sentence in msg["sentences"]:
        user_input = ConversationInput(
            text=sentence,
            context=connection.context(msg),
            conversation_id=None,
            device_id=msg.get("device_id"),
            satellite_id=None,
            language=msg.get("language", hass.config.language),
            agent_id=agent.entity_id,
        )
        result_dict = await agent.async_debug_recognize(user_input)
        result_dicts.append(result_dict)

    connection.send_result(msg["id"], {"results": result_dicts})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "conversation/agent/homeassistant/language_scores",
        vol.Optional("language"): str,
        vol.Optional("country"): str,
    }
)
@websocket_api.async_response
async def websocket_hass_agent_language_scores(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get support scores per language."""
    agent = get_agent_manager(hass).default_agent
    assert agent is not None

    language = msg.get("language", hass.config.language)
    country = msg.get("country", hass.config.country)

    scores = await agent.async_get_language_scores()
    matching_langs = language_util.matches(language, scores.keys(), country=country)
    preferred_lang = matching_langs[0] if matching_langs else language
    result = {
        "languages": {
            lang_key: asdict(lang_scores) for lang_key, lang_scores in scores.items()
        },
        "preferred_language": preferred_lang,
    }

    connection.send_result(msg["id"], result)


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
    async def post(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Send a request for processing."""
        hass = request.app[http.KEY_HASS]

        result = await async_converse(
            hass,
            text=data["text"],
            conversation_id=data.get("conversation_id"),
            context=self.context(request),
            language=data.get("language"),
            agent_id=data.get("agent_id"),
        )

        return self.json(result.as_dict())
