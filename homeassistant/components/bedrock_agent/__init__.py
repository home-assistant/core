"""The Bedrock Agent integration."""

from __future__ import annotations

from functools import partial
import json
import logging
from typing import Literal

import boto3

from homeassistant.components import conversation
from homeassistant.components.conversation import agent_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import (
    CONST_KEY_ID,
    CONST_KEY_SECRET,
    CONST_MODEL_ID,
    CONST_MODEL_LIST,
    CONST_PROMPT_CONTEXT,
    CONST_REGION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
__all__ = [
    "async_setup_entry",
    "async_unload_entry",
    "options_update_listener",
    "async_process",
    "BedrockAgent",
]


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

    @staticmethod
    def supported_models() -> list[str]:
        """Return a list of supported models."""
        return CONST_MODEL_LIST

    async def async_call_bedrock(self, question) -> str:
        """Return result from Amazon Bedrock."""

        question = self.entry.data[CONST_PROMPT_CONTEXT] + question

        modelId = self.entry.data[CONST_MODEL_ID]
        body = json.dumps({"prompt": question})

        # switch case statement
        if modelId.startswith("amazon.titan-text-express-v1"):
            body = json.dumps(
                {
                    "inputText": question,
                    "textGenerationConfig": {
                        "temperature": 0,
                        "topP": 1,
                        "maxTokenCount": 512,
                    },
                }
            )
        elif modelId.startswith("anthropic.claude"):
            body = json.dumps(
                {
                    "prompt": f"\n\nHuman:{question}\n\nAssistant:",
                    "max_tokens_to_sample": 200,
                    "temperature": 0.1,
                    "top_p": 0.9,
                }
            )
        elif modelId.startswith("ai21.j2"):
            body = json.dumps(
                {
                    "prompt": question,
                    "temperature": 0.5,
                    "topP": 0.5,
                    "maxTokens": 200,
                    "countPenalty": {"scale": 0},
                    "presencePenalty": {"scale": 0},
                    "frequencyPenalty": {"scale": 0},
                }
            )
        elif modelId.startswith("mistral.mistral-"):
            body = json.dumps(
                {
                    "prompt": f"<s>[INST] {question} [/INST]",
                    "max_tokens": 512,
                    "temperature": 0.5,
                    "top_p": 0.9,
                    "top_k": 50,
                }
            )

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
        if modelId.startswith("amazon.titan-text-express-v1"):
            answer = response_body["results"][0]["outputText"]
        elif modelId.startswith("anthropic.claude"):
            answer = response_body["completion"]
        elif modelId.startswith("ai21.j2"):
            answer = response_body["completions"][0]["data"]["text"]
        elif modelId in [
            "mistral.mistral-7b-instruct-v0:2",
            "mistral.mixtral-8x7b-instruct-v0:1",
        ]:
            answer = response_body["outputs"][0]["text"]
        else:
            answer = "Sorry I am not able to understand my underlying model."

        return answer

    async def async_process(
        self, user_input: agent_manager.ConversationInput
    ) -> agent_manager.ConversationResult:
        """Process a sentence."""
        answer = await self.async_call_bedrock(user_input.text)

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(answer)
        return agent_manager.ConversationResult(conversation_id=None, response=response)
