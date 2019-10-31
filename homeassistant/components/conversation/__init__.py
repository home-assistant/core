"""Support for functionality to have conversations with Home Assistant."""
import logging
import re

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.loader import bind_hass

from .agent import AbstractConversationAgent
from .default_agent import async_register, DefaultAgent

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = "text"

DOMAIN = "conversation"

REGEX_TYPE = type(re.compile(""))
DATA_AGENT = "conversation_agent"

SERVICE_PROCESS = "process"

SERVICE_PROCESS_SCHEMA = vol.Schema({vol.Required(ATTR_TEXT): cv.string})

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


async_register = bind_hass(async_register)  # pylint: disable=invalid-name


@core.callback
@bind_hass
def async_set_agent(hass: core.HomeAssistant, agent: AbstractConversationAgent):
    """Set the agent to handle the conversations."""
    hass.data[DATA_AGENT] = agent


async def async_setup(hass, config):
    """Register the process service."""

    async def process(hass, text):
        """Process a line of text."""
        agent = hass.data.get(DATA_AGENT)

        if agent is None:
            agent = hass.data[DATA_AGENT] = DefaultAgent(hass)
            await agent.async_initialize(config)

        return await agent.async_process(text)

    async def handle_service(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        try:
            await process(hass, text)
        except intent.IntentHandleError as err:
            _LOGGER.error("Error processing %s: %s", text, err)

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, handle_service, schema=SERVICE_PROCESS_SCHEMA
    )

    hass.http.register_view(ConversationProcessView(process))

    return True


class ConversationProcessView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = "/api/conversation/process"
    name = "api:conversation:process"

    def __init__(self, process):
        """Initialize the conversation process view."""
        self._process = process

    @RequestDataValidator(vol.Schema({vol.Required("text"): str}))
    async def post(self, request, data):
        """Send a request for processing."""
        hass = request.app["hass"]

        try:
            intent_result = await self._process(hass, data["text"])
        except intent.IntentHandleError as err:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech(str(err))

        if intent_result is None:
            # ais-dom ask
            from homeassistant.components import ais_ai_service as ais_ai

            intent_result = await ais_ai._process(hass, data["text"])
            if intent_result is None:
                intent_result = intent.IntentResponse()
                intent_result.async_set_speech(
                    "Przepraszam, jeszcze tego nie potrafię zrozumieć."
                )

        return self.json(intent_result)
