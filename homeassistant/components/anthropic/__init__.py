"""The Anthropic integration."""

from __future__ import annotations

from functools import partial

import anthropic

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_CHAT_MODEL, DOMAIN, LOGGER, RECOMMENDED_CHAT_MODEL

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AnthropicConfigEntry = ConfigEntry[anthropic.AsyncClient]


async def async_setup_entry(hass: HomeAssistant, entry: AnthropicConfigEntry) -> bool:
    """Set up Anthropic from a config entry."""
    client = await hass.async_add_executor_job(
        partial(anthropic.AsyncAnthropic, api_key=entry.data[CONF_API_KEY])
    )
    try:
        model_id = entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        model = await client.models.retrieve(model_id=model_id, timeout=10.0)
        LOGGER.debug("Anthropic model: %s", model.display_name)
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
