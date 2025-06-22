"""The Ollama integration."""

from __future__ import annotations

import asyncio
import logging

import httpx
import ollama

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util.ssl import get_default_context

from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    CONF_THINK,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONF_KEEP_ALIVE",
    "CONF_MAX_HISTORY",
    "CONF_MODEL",
    "CONF_NUM_CTX",
    "CONF_PROMPT",
    "CONF_THINK",
    "CONF_URL",
    "DOMAIN",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ollama from a config entry."""
    settings = {**entry.data, **entry.options}
    client = ollama.AsyncClient(host=settings[CONF_URL], verify=get_default_context())
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.list()
    except (TimeoutError, httpx.ConnectError) as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1:
        # Migrate from version 1 to version 2
        # Move conversation-specific options to a subentry
        subentry = ConfigSubentry(
            data=entry.options,
            subentry_type="conversation",
            title=DEFAULT_CONVERSATION_NAME,
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(
            entry,
            subentry,
        )

        # Migrate conversation entity to be linked to subentry
        ent_reg = er.async_get(hass)
        conversation_entity = ent_reg.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        if conversation_entity is not None:
            ent_reg.async_update_entity(
                conversation_entity,
                config_subentry_id=subentry.subentry_id,
                new_unique_id=subentry.subentry_id,
            )

        # Remove options from the main entry
        hass.config_entries.async_update_entry(
            entry,
            options={},
            version=2,
        )

    return True
