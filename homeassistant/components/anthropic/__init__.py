"""The Anthropic integration."""

from __future__ import annotations

from functools import partial

import anthropic

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHAT_MODEL,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
)

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AnthropicConfigEntry = ConfigEntry[anthropic.AsyncClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Anthropic."""
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AnthropicConfigEntry) -> bool:
    """Set up Anthropic from a config entry."""
    client = await hass.async_add_executor_job(
        partial(anthropic.AsyncAnthropic, api_key=entry.data[CONF_API_KEY])
    )
    try:
        # Use model from first conversation subentry for validation
        subentries = list(entry.subentries.values())
        if subentries:
            model_id = subentries[0].data.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        else:
            model_id = RECOMMENDED_CHAT_MODEL
        model = await client.models.retrieve(model_id=model_id, timeout=10.0)
        LOGGER.debug("Anthropic model: %s", model.display_name)
    except anthropic.AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        return False
    except anthropic.AnthropicError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Anthropic."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: AnthropicConfigEntry
) -> None:
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

    api_keys_entries: dict[str, tuple[ConfigEntry, bool]] = {}
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
        if entry.data[CONF_API_KEY] not in api_keys_entries:
            use_existing = True
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
            )
            api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]

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
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_CONVERSATION_NAME,
                options={},
                version=2,
                minor_version=3,
            )


async def async_migrate_entry(hass: HomeAssistant, entry: AnthropicConfigEntry) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version > 2:
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

    LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True
