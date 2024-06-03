"""The OpenAI Conversation integration."""

from __future__ import annotations

import openai

from homeassistant.components.openai_conversation import OpenAIConfigEntry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import AZURE_OPEN_API_VERSION, CONF_AZURE_OPENAI_RESOURCE, DOMAIN, LOGGER

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: OpenAIConfigEntry) -> bool:
    """Set up Azure OpenAI Conversation from a config entry."""
    client = openai.AsyncAzureOpenAI(
        azure_endpoint=f"https://{entry.data[CONF_AZURE_OPENAI_RESOURCE]}.openai.azure.com",
        api_key=str(entry.data[CONF_API_KEY]),
        api_version=AZURE_OPEN_API_VERSION,
    )
    try:
        await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)
    except openai.AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        return False
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
