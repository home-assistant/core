"""The LM Studio integration."""

from __future__ import annotations

import logging

import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)

type LMStudioConfigEntry = ConfigEntry[openai.AsyncOpenAI]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up LM Studio."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LMStudioConfigEntry) -> bool:
    """Set up LM Studio from a config entry."""
    base_url = entry.data[CONF_BASE_URL]
    api_key = entry.data[CONF_API_KEY]

    client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=get_async_client(hass),
    )

    try:
        # Test the connection by listing models
        await client.with_options(timeout=10.0).models.list()
    except openai.AuthenticationError as err:
        _LOGGER.error("Authentication failed: %s", err)
        return False
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(f"Failed to connect to LM Studio: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
