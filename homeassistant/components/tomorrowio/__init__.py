"""The Tomorrow.io integration."""

from types import MappingProxyType

from pytomorrowio import TomorrowioV4

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_TIMESTEP,
    DEFAULT_TIMESTEP,
    DOMAIN,
    INTEGRATION_NAME,
    SUBENTRY_TYPE_LOCATION,
)
from .coordinator import TomorrowioConfigEntry, TomorrowioDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tomorrow.io integration."""
    await async_migrate_integration(hass)
    return True


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate to one config entry per API key with location subentries."""
    # Make sure we get enabled config entries first
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, tuple[TomorrowioConfigEntry, bool]] = {}
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # A previous run may have been interrupted: entries already migrated to
    # version 2 become parents for any v1 siblings still sharing their key.
    for entry in entries:
        if entry.version != 1:
            api_keys_entries.setdefault(
                entry.data[CONF_API_KEY], (entry, entry.disabled_by is not None)
            )

    for entry in entries:
        if entry.version != 1:
            continue
        api_key = entry.data[CONF_API_KEY]
        location = entry.data[CONF_LOCATION]

        # The title reflects UI renames while data[CONF_NAME] is frozen at
        # creation, so the title is the user's current name for the location.
        # Default titles were "Tomorrow.io - <zone>"; under a parent entry
        # already titled Tomorrow.io only the zone part is meaningful.
        name = entry.title.removeprefix(f"{INTEGRATION_NAME} - ") or entry.title

        subentry = ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_LOCATION: location,
                    CONF_NAME: name,
                    CONF_TIMESTEP: entry.options.get(CONF_TIMESTEP, DEFAULT_TIMESTEP),
                }
            ),
            subentry_type=SUBENTRY_TYPE_LOCATION,
            title=name,
            unique_id=f"{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}",
        )

        if api_key not in api_keys_entries:
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == api_key
            )
            api_keys_entries[api_key] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[api_key]

        if existing_subentry := next(
            (
                existing
                for existing in parent_entry.get_subentries_of_type(
                    SUBENTRY_TYPE_LOCATION
                )
                if existing.unique_id == subentry.unique_id
            ),
            None,
        ):
            # An interrupted earlier run already persisted this subentry but
            # not yet the removal of its source entry; finish that work.
            subentry = existing_subentry
        else:
            hass.config_entries.async_add_subentry(parent_entry, subentry)

        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        device = devices[0] if devices else None

        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
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

        if device:
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
                # The old identifiers, based on the API key, are not unique per
                # location so each location device is re-identified by its subentry
                new_identifiers={(DOMAIN, subentry.subentry_id)},
                new_config_entry_id=parent_entry.entry_id,
                new_config_subentry_id=subentry.subentry_id,
            )

        if parent_entry.entry_id != entry.entry_id:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            hass.config_entries.async_update_entry(
                entry,
                data={CONF_API_KEY: api_key},
                options={},
                title=INTEGRATION_NAME,
                unique_id=api_key,
                version=2,
            )


async def async_setup_entry(hass: HomeAssistant, entry: TomorrowioConfigEntry) -> bool:
    """Set up Tomorrow.io API from a config entry."""
    session = async_get_clientsession(hass)
    # we will not use the class's lat and long so we can pass in garbage
    # lats and longs
    api = TomorrowioV4(
        entry.data[CONF_API_KEY], 361.0, 361.0, unit_system="metric", session=session
    )
    coordinator = TomorrowioDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: TomorrowioConfigEntry
) -> None:
    """Reload the config entry when subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TomorrowioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
