"""The llama.cpp integration."""

import logging

import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .api import async_create_client, async_list_models

_LOGGER = logging.getLogger(__name__)
PLATFORMS = (Platform.CONVERSATION,)

type LlamaCppConfigEntry = ConfigEntry[openai.AsyncOpenAI]


async def async_setup_entry(hass: HomeAssistant, entry: LlamaCppConfigEntry) -> bool:
    """Set up llama.cpp from a config entry."""
    client = await async_create_client(hass, entry.data)

    # Validate the connection by listing models
    try:
        await async_list_models(client)
    except HomeAssistantError as err:
        if err.translation_key == "invalid_auth":
            raise ConfigEntryAuthFailed(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LlamaCppConfigEntry) -> bool:
    """Unload llama.cpp."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: LlamaCppConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
