"""HTTP endpoints for conversation integration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from aiohttp import web
from hassil.recognize import (
    MISSING_ENTITY,
    RecognizeResult,
    UnmatchedRangeEntity,
    UnmatchedTextEntity,
)
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import language as language_util

from .agent_manager import (
    agent_id_validator,
    async_converse,
    async_get_agent,
    get_agent_manager,
)
from .const import DOMAIN
from .default_agent import (
    METADATA_CUSTOM_FILE,
    METADATA_CUSTOM_SENTENCE,
    DefaultAgent,
    SentenceTriggerResult,
    async_get_default_agent,
)
from .entity import ConversationEntity
from .models import ConversationInput


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    hass.http.register_view(ConversationProcessView())
    websocket_api.async_register_command(hass, websocket_process)
    websocket_api.async_register_command(hass, websocket_prepare)
    websocket_api.async_register_command(hass, websocket_list_agents)
    websocket_api.async_register_command(hass, websocket_hass_agent_debug)


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
    entity_component: EntityComponent[ConversationEntity] = hass.data[DOMAIN]

    country = msg.get("country")
    language = msg.get("language")
    agents = []

    for entity in entity_component.entities:
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
    agent = async_get_default_agent(hass)
    assert isinstance(agent, DefaultAgent)
    results = [
        await agent.async_recognize(
            ConversationInput(
                text=sentence,
                context=connection.context(msg),
                conversation_id=None,
                device_id=msg.get("device_id"),
                language=msg.get("language", hass.config.language),
                agent_id=None,
            )
        )
        for sentence in msg["sentences"]
    ]

    # Return results for each sentence in the same order as the input.
    result_dicts: list[dict[str, Any] | None] = []
    for result in results:
        result_dict: dict[str, Any] | None = None
        if isinstance(result, SentenceTriggerResult):
            result_dict = {
                # Matched a user-defined sentence trigger.
                # We can't provide the response here without executing the
                # trigger.
                "match": True,
                "source": "trigger",
                "sentence_template": result.sentence_template or "",
            }
        elif isinstance(result, RecognizeResult):
            successful_match = not result.unmatched_entities
            result_dict = {
                # Name of the matching intent (or the closest)
                "intent": {
                    "name": result.intent.name,
                },
                # Slot values that would be received by the intent
                "slots": {  # direct access to values
                    entity_key: entity.text or entity.value
                    for entity_key, entity in result.entities.items()
                },
                # Extra slot details, such as the originally matched text
                "details": {
                    entity_key: {
                        "name": entity.name,
                        "value": entity.value,
                        "text": entity.text,
                    }
                    for entity_key, entity in result.entities.items()
                },
                # Entities/areas/etc. that would be targeted
                "targets": {},
                # True if match was successful
                "match": successful_match,
                # Text of the sentence template that matched (or was closest)
                "sentence_template": "",
                # When match is incomplete, this will contain the best slot guesses
                "unmatched_slots": _get_unmatched_slots(result),
            }

            if successful_match:
                result_dict["targets"] = {
                    state.entity_id: {"matched": is_matched}
                    for state, is_matched in _get_debug_targets(hass, result)
                }

            if result.intent_sentence is not None:
                result_dict["sentence_template"] = result.intent_sentence.text

            # Inspect metadata to determine if this matched a custom sentence
            if result.intent_metadata and result.intent_metadata.get(
                METADATA_CUSTOM_SENTENCE
            ):
                result_dict["source"] = "custom"
                result_dict["file"] = result.intent_metadata.get(METADATA_CUSTOM_FILE)
            else:
                result_dict["source"] = "builtin"

        result_dicts.append(result_dict)

    connection.send_result(msg["id"], {"results": result_dicts})


def _get_debug_targets(
    hass: HomeAssistant,
    result: RecognizeResult,
) -> Iterable[tuple[State, bool]]:
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

    if (
        (name is None)
        and (area_name is None)
        and (not domains)
        and (not device_classes)
        and (not state_names)
    ):
        # Avoid "matching" all entities when there is no filter
        return

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


def _get_unmatched_slots(
    result: RecognizeResult,
) -> dict[str, str | int | float]:
    """Return a dict of unmatched text/range slot entities."""
    unmatched_slots: dict[str, str | int | float] = {}
    for entity in result.unmatched_entities_list:
        if isinstance(entity, UnmatchedTextEntity):
            if entity.text == MISSING_ENTITY:
                # Don't report <missing> since these are just missing context
                # slots.
                continue

            unmatched_slots[entity.name] = entity.text
        elif isinstance(entity, UnmatchedRangeEntity):
            unmatched_slots[entity.name] = entity.value

    return unmatched_slots


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
