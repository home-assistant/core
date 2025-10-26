"""The Ollama integration."""

from __future__ import annotations

import asyncio
import logging
from types import MappingProxyType

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
    DEFAULT_AI_TASK_NAME,
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
PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)

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

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    return True


async def async_update_options(hass: HomeAssistant, entry: OllamaConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure."""

    # Make sure we get enabled config entries first
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return

    url_entries: dict[str, tuple[ConfigEntry, bool]] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        use_existing = False
        # Create subentry with model from entry.data and options from entry.options
        subentry_data = entry.options.copy()
        subentry_data[CONF_MODEL] = entry.data[CONF_MODEL]

        subentry = ConfigSubentry(
            data=MappingProxyType(subentry_data),
            subentry_type="conversation",
            title=entry.title,
            unique_id=None,
        )
        if entry.data[CONF_URL] not in url_entries:
            use_existing = True
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_URL] == entry.data[CONF_URL]
            )
            url_entries[entry.data[CONF_URL]] = (entry, all_disabled)

        parent_entry, all_disabled = url_entries[entry.data[CONF_URL]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)

        conversation_entity_id = entity_registry.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )

        if conversation_entity_id is not None:
            conversation_entity_entry = entity_registry.entities[conversation_entity_id]
            entity_disabled_by = conversation_entity_entry.disabled_by
            if (
                entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                # Device and entity registries will set the disabled_by flag to None
                # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
                # config entry, but we want to set it to DEVICE or USER instead,
                entity_disabled_by = (
                    er.RegistryEntryDisabler.DEVICE
                    if device
                    else er.RegistryEntryDisabler.USER
                )
            entity_registry.async_update_entity(
                conversation_entity_id,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                disabled_by=entity_disabled_by,
                new_unique_id=subentry.subentry_id,
            )

        if device is not None:
            # Device and entity registries will set the disabled_by flag to None
            # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
            # config entry, but we want to set it to USER instead,
            device_disabled_by = device.disabled_by
            if (
                device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                device_disabled_by = dr.DeviceEntryDisabler.USER
            device_registry.async_update_device(
                device.id,
                disabled_by=device_disabled_by,
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
            _add_ai_task_subentry(hass, entry)
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_NAME,
                # Update parent entry to only keep URL, remove model
                data={CONF_URL: entry.data[CONF_URL]},
                options={},
                version=3,
                minor_version=3,
            )


async def async_migrate_entry(hass: HomeAssistant, entry: OllamaConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version > 3:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 2 and entry.minor_version == 1:
        # Correct broken device migration in Home Assistant Core 2025.7.0b0-2025.7.0b1
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            device_registry.async_update_device(
                device.id,
                remove_config_entry_id=entry.entry_id,
                remove_config_subentry_id=None,
            )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    if entry.version == 2 and entry.minor_version == 2:
        # Update subentries to include the model
        for subentry in entry.subentries.values():
            if subentry.subentry_type == "conversation":
                updated_data = dict(subentry.data)
                updated_data[CONF_MODEL] = entry.data[CONF_MODEL]

                hass.config_entries.async_update_subentry(
                    entry, subentry, data=MappingProxyType(updated_data)
                )

        # Update main entry to remove model and bump version
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_URL: entry.data[CONF_URL]},
            version=3,
            minor_version=1,
        )

    if entry.version == 3 and entry.minor_version == 1:
        _add_ai_task_subentry(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    if entry.version == 3 and entry.minor_version == 2:
        # Fix migration where the disabled_by flag was not set correctly.
        # We can currently only correct this for enabled config entries,
        # because migration does not run for disabled config entries. This
        # is asserted in tests, and if that behavior is changed, we should
        # correct also disabled config entries.
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entry.disabled_by is None:
            # If the config entry is not disabled, we need to set the disabled_by
            # flag on devices to USER, and on entities to DEVICE, if they are set
            # to CONFIG_ENTRY.
            for device in devices:
                if device.disabled_by is not dr.DeviceEntryDisabler.CONFIG_ENTRY:
                    continue
                device_registry.async_update_device(
                    device.id,
                    disabled_by=dr.DeviceEntryDisabler.USER,
                )
            for entity in entity_entries:
                if entity.disabled_by is not er.RegistryEntryDisabler.CONFIG_ENTRY:
                    continue
                entity_registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.DEVICE,
                )
        hass.config_entries.async_update_entry(entry, minor_version=3)

    _LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True


def _add_ai_task_subentry(hass: HomeAssistant, entry: OllamaConfigEntry) -> None:
    """Add AI Task subentry to the config entry."""
    # Add AI Task subentry with default options. We can only create a new
    # subentry if we can find an existing model in the entry. The model
    # was removed in the previous migration step, so we need to
    # check the subentries for an existing model.
    existing_model = next(
        iter(
            model
            for subentry in entry.subentries.values()
            if (model := subentry.data.get(CONF_MODEL)) is not None
        ),
        None,
    )
    if existing_model:
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_MODEL: existing_model}),
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
        )
