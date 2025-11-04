"""The World Air Quality Index (WAQI) integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from aiowaqi import WAQIClient

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_NUMBER, DOMAIN, SUBENTRY_TYPE_STATION
from .coordinator import WAQIConfigEntry, WAQIDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WAQI."""

    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WAQIConfigEntry) -> bool:
    """Set up World Air Quality Index (WAQI) from a config entry."""

    client = WAQIClient(session=async_get_clientsession(hass))
    client.authenticate(entry.data[CONF_API_KEY])

    entry.runtime_data = {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_STATION:
            continue

        # Create a coordinator for each station subentry
        coordinator = WAQIDataUpdateCoordinator(hass, entry, subentry, client)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data[subentry.subentry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(hass: HomeAssistant, entry: WAQIConfigEntry) -> None:
    """Update entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WAQIConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure to subentries."""

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
        subentry = ConfigSubentry(
            data=MappingProxyType(
                {CONF_STATION_NUMBER: entry.data[CONF_STATION_NUMBER]}
            ),
            subentry_type="station",
            title=entry.title,
            unique_id=entry.unique_id,
        )
        if entry.data[CONF_API_KEY] not in api_keys_entries:
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
            )
            api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)

        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if TYPE_CHECKING:
            assert entry.unique_id is not None
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.unique_id)}
        )

        for entity_entry in entities:
            entity_disabled_by = entity_entry.disabled_by
            if (
                entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                # Device and entity registries don't update the disabled_by flag
                # when moving a device or entity from one config entry to another,
                # so we need to do it manually.
                entity_disabled_by = (
                    er.RegistryEntryDisabler.DEVICE
                    if device
                    else er.RegistryEntryDisabler.USER
                )
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                disabled_by=entity_disabled_by,
            )

        if device is not None:
            # Device and entity registries don't update the disabled_by flag when
            # moving a device or entity from one config entry to another, so we
            # need to do it manually.
            device_disabled_by = device.disabled_by
            if (
                device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                device_disabled_by = dr.DeviceEntryDisabler.USER
            device_registry.async_update_device(
                device.id,
                disabled_by=device_disabled_by,
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

        if parent_entry.entry_id != entry.entry_id:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            hass.config_entries.async_update_entry(
                entry,
                title="WAQI",
                version=2,
                data={CONF_API_KEY: entry.data[CONF_API_KEY]},
                unique_id=None,
            )
