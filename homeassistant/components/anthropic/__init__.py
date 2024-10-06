"""The Anthropic integration."""

from __future__ import annotations

import anthropic

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, LOGGER

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AnthropicConfigEntry = ConfigEntry[anthropic.AsyncClient]


async def async_setup_entry(hass: HomeAssistant, entry: AnthropicConfigEntry) -> bool:
    """Set up Anthropic from a config entry."""
    client = anthropic.AsyncAnthropic(api_key=entry.data[CONF_API_KEY])
    try:
        await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}],
            timeout=10.0,
        )
    except anthropic.AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        return False
    except anthropic.AnthropicError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Anthropic."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
