"""The OpenRouter integration."""

from __future__ import annotations

from openai import AsyncOpenAI, AuthenticationError, OpenAIError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import (
    HomeAssistant,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    LOGGER,
)

PLATFORMS = [Platform.CONVERSATION]

type OpenRouterConfigEntry = ConfigEntry[AsyncOpenAI]


async def async_setup_entry(hass: HomeAssistant, entry: OpenRouterConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=entry.data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )

    # Cache current platform data which gets added to each request (caching done by library)
    _ = await hass.async_add_executor_job(client.platform_headers)

    try:
        await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)
    except AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        return False
    except OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
