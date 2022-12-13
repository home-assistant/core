"""Support for functionality to have conversations with Home Assistant."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http, websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent import AbstractConversationAgent, ConversationResult
from .default_agent import DefaultAgent, async_register

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = "text"
ATTR_LANGUAGE = "language"

DOMAIN = "conversation"

REGEX_TYPE = type(re.compile(""))
DATA_AGENT = "conversation_agent"
DATA_CONFIG = "conversation_config"

SERVICE_PROCESS = "process"

SERVICE_PROCESS_SCHEMA = vol.Schema(
    {vol.Required(ATTR_TEXT): cv.string, vol.Optional(ATTR_LANGUAGE): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("intents"): vol.Schema(
                    {cv.string: vol.All(cv.ensure_list, [cv.string])}
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async_register = bind_hass(async_register)


@core.callback
@bind_hass
def async_set_agent(hass: core.HomeAssistant, agent: AbstractConversationAgent | None):
    """Set the agent to handle the conversations."""
    hass.data[DATA_AGENT] = agent


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    hass.data[DATA_CONFIG] = config

    async def handle_service(service: core.ServiceCall) -> None:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        agent = await _get_agent(hass)
        try:
            await agent.async_process(
                text, service.context, language=service.data.get(ATTR_LANGUAGE)
            )
        except intent.IntentHandleError as err:
            _LOGGER.error("Error processing %s: %s", text, err)

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, handle_service, schema=SERVICE_PROCESS_SCHEMA
    )
    hass.http.register_view(ConversationProcessView())
    websocket_api.async_register_command(hass, websocket_process)
    websocket_api.async_register_command(hass, websocket_get_agent_info)
    websocket_api.async_register_command(hass, websocket_set_onboarding)

    return True


@websocket_api.websocket_command(
    {
        "type": "conversation/process",
        "text": str,
        vol.Optional("conversation_id"): str,
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
    result = await _async_converse(
        hass,
        msg["text"],
        msg.get("conversation_id"),
        connection.context(msg),
        msg.get("language"),
    )
    connection.send_result(msg["id"], result.as_dict())


@websocket_api.websocket_command({"type": "conversation/agent/info"})
@websocket_api.async_response
async def websocket_get_agent_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Do we need onboarding."""
    agent = await _get_agent(hass)

    connection.send_result(
        msg["id"],
        {
            "onboarding": await agent.async_get_onboarding(),
            "attribution": agent.attribution,
        },
    )


@websocket_api.websocket_command({"type": "conversation/onboarding/set", "shown": bool})
@websocket_api.async_response
async def websocket_set_onboarding(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set onboarding status."""
    agent = await _get_agent(hass)

    success = await agent.async_set_onboarding(msg["shown"])

    if success:
        connection.send_result(msg["id"])
    else:
        connection.send_error(msg["id"], "error", "Failed to set onboarding")


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
        result = await _async_converse(
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


async def _async_converse(
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

    result: ConversationResult | None = None
    intent_response: intent.IntentResponse | None = None

    try:
        result = await agent.async_process(text, context, conversation_id, language)
    except intent.IntentHandleError as err:
        # Match was successful, but target(s) were invalid
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_error(
            intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            str(err),
        )
    except intent.IntentUnexpectedError as err:
        # Match was successful, but an error occurred while handling intent
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_error(
            intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
            str(err),
        )
    except intent.IntentError as err:
        # Unknown error
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_error(
            intent.IntentResponseErrorCode.UNKNOWN,
            str(err),
        )

    if result is None:
        if intent_response is None:
            # Match was not successful
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                "Sorry, I didn't understand that",
            )

        result = ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    return result
