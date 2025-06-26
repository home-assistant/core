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
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import get_default_context

from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    CONF_THINK,
    DEFAULT_NAME,
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

type OllamaConfigEntry = ConfigEntry[ollama.AsyncClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Ollama."""
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OllamaConfigEntry) -> bool:
    """Set up Ollama from a config entry."""
    settings = {**entry.data, **entry.options}
    client = ollama.AsyncClient(host=settings[CONF_URL], verify=get_default_context())
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.list()
    except (TimeoutError, httpx.ConnectError) as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    return True


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure."""

    entries = hass.config_entries.async_entries(DOMAIN)
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, ConfigEntry] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        use_existing = False
        subentry = ConfigSubentry(
            data=entry.options,
            subentry_type="conversation",
            title=entry.title,
            unique_id=None,
        )
        if entry.data[CONF_URL] not in api_keys_entries:
            use_existing = True
            api_keys_entries[entry.data[CONF_URL]] = entry

        parent_entry = api_keys_entries[entry.data[CONF_URL]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)
        conversation_entity = entity_registry.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        if conversation_entity is not None:
            entity_registry.async_update_entity(
                conversation_entity,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                new_unique_id=subentry.subentry_id,
            )

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                new_identifiers={(DOMAIN, subentry.subentry_id)},
                add_config_subentry_id=subentry.subentry_id,
                add_config_entry_id=parent_entry.entry_id,
            )
            if parent_entry.entry_id != entry.entry_id:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                )
            else:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                    remove_config_subentry_id=None,
                )

        if not use_existing:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_NAME,
                options={},
                version=2,
            )
