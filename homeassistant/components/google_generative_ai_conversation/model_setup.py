"""Generic helper functions for setting up Gemini models."""

from google.genai import Client
from google.genai.types import GenerateContentConfig, HarmCategory, SafetySetting

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)

type GoogleGenerativeAIConfigEntry = ConfigEntry[Client]


def get_content_config(
    entry: GoogleGenerativeAIConfigEntry,
) -> GenerateContentConfig:
    """Create parameters for Gemini model inputs from a config entry."""

    return GenerateContentConfig(
        temperature=entry.options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
        top_k=entry.options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
        top_p=entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
        max_output_tokens=entry.options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
        safety_settings=[
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=entry.options.get(
                    CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=entry.options.get(
                    CONF_HARASSMENT_BLOCK_THRESHOLD,
                    RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=entry.options.get(
                    CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=entry.options.get(
                    CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
            ),
        ],
    )
