"""Config flow for OpenAI Conversation integration."""

from __future__ import annotations

import logging
from typing import Any, override

import openai
import voluptuous as vol

from homeassistant.components.openai_conversation.config_flow import (
    OpenAIConfigFlow,
    OpenAIOptionsFlow,
)
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import (
    AZURE_OPEN_API_VERSION,
    CONF_AZURE_OPENAI_RESOURCE,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AZURE_OPENAI_RESOURCE): str,
        vol.Required(CONF_API_KEY): str,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


class AzureOpenAIConfigFlow(OpenAIConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure OpenAI Conversation."""

    step_user_data_schema = STEP_USER_DATA_SCHEMA

    @override
    async def validate_input(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Validate the user input allows us to connect."""
        client = openai.AsyncAzureOpenAI(
            azure_endpoint=f"https://{data[CONF_AZURE_OPENAI_RESOURCE]}.openai.azure.com",
            api_key=str(data[CONF_API_KEY]),
            api_version=AZURE_OPEN_API_VERSION,
        )
        await self.hass.async_add_executor_job(
            client.with_options(timeout=10.0).models.list
        )

    @staticmethod
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return AzureOpenAIOptionsFlow(config_entry)


class AzureOpenAIOptionsFlow(OpenAIOptionsFlow):
    """Options flow based on Open AI."""

    default_recommended_chat_model = RECOMMENDED_CHAT_MODEL
    default_recommended_max_tokens = RECOMMENDED_MAX_TOKENS
    default_recommended_top_p = RECOMMENDED_TOP_P
    default_recommended_temperature = RECOMMENDED_TEMPERATURE
