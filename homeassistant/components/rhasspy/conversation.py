"""
Rhasspy agent for conversation integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
from abc import ABC
import logging
from typing import Optional

import pydash
from rhasspyclient import RhasspyClient

from homeassistant import core
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class RhasspyConversationAgent(ABC):
    """Rhasspy conversation agent."""

    def __init__(self, hass: core.HomeAssistant, api_url: str):
        """Initialize the conversation agent."""
        self.hass = hass
        self.api_url = api_url

    async def async_process(
        self, text: str, conversation_id: Optional[str] = None
    ) -> intent.IntentResponse:
        """Process a sentence."""
        _LOGGER.debug("Processing '%s'", text)

        session = async_get_clientsession(self.hass)
        client = RhasspyClient(self.api_url, session)
        result = await client.text_to_intent(text)
        intent_type = pydash.get(result, "intent.name", "")
        if len(intent_type) > 0:
            _LOGGER.debug(result)

            text = result.get("raw_text", result.get("text", ""))
            slots = result.get("slots", {})

            return await intent.async_handle(
                self.hass,
                DOMAIN,
                intent_type,
                {key: {"value": value} for key, value in slots.items()},
                text,
            )

        # Don't try to handle an empty intent
        _LOGGER.warning("Received empty intent")
