"""The Bedrock Agent integration."""
from __future__ import annotations

from functools import partial
import json
import logging
from typing import Literal

import boto3

from homeassistant.components import conversation
from homeassistant.components.conversation import agent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import CONST_KEY_ID, CONST_KEY_SECRET, CONST_MODEL_ID, CONST_REGION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bedrock Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    conversation.async_set_agent(hass, entry, BedrockAgent(hass, entry))

    hass_data = dict(entry.data)
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    conversation.async_unset_agent(hass, entry)
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class BedrockAgent(conversation.AbstractConversationAgent):
    """Bedrock conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.entry.data[CONST_REGION],
            aws_access_key_id=self.entry.data[CONST_KEY_ID],
            aws_secret_access_key=self.entry.data[CONST_KEY_SECRET],
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_call_bedrock(self, question) -> str:
        """Return result from Amazon Bedrock."""

        body = json.dumps(
            {
                "prompt": f"\n\nHuman:{question}\n\nAssistant:",
                "max_tokens_to_sample": 300,
                "temperature": 0.1,
                "top_p": 0.9,
            }
        )
        modelId = self.entry.data[CONST_MODEL_ID]
        accept = "application/json"
        contentType = "application/json"

        bedrock_response = await self.hass.async_add_executor_job(
            partial(
                self.bedrock.invoke_model,
                body=body,
                modelId=modelId,
                accept=accept,
                contentType=contentType,
            ),
        )

        response_body = json.loads(bedrock_response.get("body").read())
        return response_body["completion"]

    async def async_process(
        self, user_input: agent.ConversationInput
    ) -> agent.ConversationResult:
        """Process a sentence."""
        answer = await self.async_call_bedrock(user_input.text)

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(answer)
        return agent.ConversationResult(conversation_id=None, response=response)
