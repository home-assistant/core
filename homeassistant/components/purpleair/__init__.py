"""The PurpleAir integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SENSOR, CONF_SENSOR_INDEX, DOMAIN, LOGGER, SCHEMA_VERSION, TITLE
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

PLATFORMS: Final[list[str]] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up PurpleAir."""
    # _config is required by the platform interface but not used here
    # since we only handle config entry setup via async_setup_entry
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Set up PurpleAir config entry."""
    coordinator = PurpleAirDataUpdateCoordinator(
        hass,
        entry,
    )
    entry.runtime_data = coordinator

    if len(entry.subentries) > 0:
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry."""

    # v1 schema:
    #   Sensor indices in options as a list of integers, duplicates are allowed and
    #   will not be removed during migration
    #   API key in data as a string, no duplicate API keys allowed
    CONF_SENSOR_INDICES: Final[str] = "sensor_indices"

    # v2 schema:
    #   One or more config subentries, each subentry has a single sensor index,
    #   no duplicate sensors allowed
    #   API key in data as a string, no duplicate API keys allowed

    # Sort enabled entries first so we pick a stable parent per API key
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda entry: entry.disabled_by is not None,
    )

    if not any(entry.version == 1 for entry in entries):
        return

    # Track the chosen parent entry and whether all siblings are disabled
    api_key_entries: dict[str, tuple[ConfigEntry, bool]] = {}
    # Merge show_on_map across siblings that share the same API key
    show_on_map_by_api_key: dict[str, bool] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        api_key = entry.data[CONF_API_KEY]
        if api_key not in api_key_entries:
            # Pick the first entry (enabled if present) as parent
            all_disabled = all(
                candidate.disabled_by is not None
                for candidate in entries
                if candidate.data[CONF_API_KEY] == api_key
            )
            api_key_entries[api_key] = (entry, all_disabled)
            show_on_map_by_api_key[api_key] = entry.options.get(CONF_SHOW_ON_MAP, False)
        else:
            show_on_map_by_api_key[api_key] = show_on_map_by_api_key[
                api_key
            ] or entry.options.get(CONF_SHOW_ON_MAP, False)

        if entry.version != 1 or entry.disabled_by is None:
            continue

        sensor_indices: list[int] | None = entry.options.get(CONF_SENSOR_INDICES)
        if not sensor_indices:
            LOGGER.warning("No sensors registered in configuration")
            hass.config_entries.async_update_entry(
                entry,
                version=SCHEMA_VERSION,
            )
            continue

        parent_entry, all_disabled = api_key_entries[api_key]

        for sensor_index in sensor_indices:
            # Skip if this sensor index already exists as a subentry
            if any(
                int(subentry.data[CONF_SENSOR_INDEX]) == sensor_index
                for subentry in parent_entry.subentries.values()
            ):
                continue

            device = device_registry.async_get_device(
                identifiers={(DOMAIN, str(sensor_index))}
            )
            subentry = ConfigSubentry(
                data=MappingProxyType({CONF_SENSOR_INDEX: sensor_index}),
                subentry_type=CONF_SENSOR,
                title=(
                    f"{device.name} ({sensor_index})"
                    if device and device.name
                    else f"Sensor {sensor_index}"
                ),
                unique_id=str(sensor_index),
            )

            # Create subentry under the chosen parent
            hass.config_entries.async_add_subentry(parent_entry, subentry)

            if device is not None:
                # Move entities tied to the old device to the new subentry
                entity_entries = er.async_entries_for_device(
                    entity_registry,
                    device.id,
                    include_disabled_entities=True,
                )

                for entity_entry in entity_entries:
                    entity_disabled_by = entity_entry.disabled_by
                    if (
                        entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                        and not all_disabled
                    ):
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

                device_disabled_by = device.disabled_by
                if (
                    device_disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                    and not all_disabled
                ):
                    device_disabled_by = dr.DeviceEntryDisabler.USER

                device_registry.async_update_device(
                    device.id,
                    disabled_by=device_disabled_by,
                    add_config_entry_id=parent_entry.entry_id,
                    add_config_subentry_id=subentry.subentry_id,
                )

                if parent_entry.entry_id != entry.entry_id:
                    # Fully detach device from the migrated sibling entry
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
            # Remove the sibling entry after rehoming its sensors
            await hass.config_entries.async_remove(entry.entry_id)
            continue

        title: str = TITLE
        config_list = hass.config_entries.async_entries(
            domain=DOMAIN, include_disabled=True, include_ignore=True
        )
        if len(config_list) > 1:
            title = f"{TITLE} ({entry.title})"

        # Update the parent entry to the new schema
        hass.config_entries.async_update_entry(
            entry,
            title=title,
            unique_id=entry.data[CONF_API_KEY],
            data={CONF_API_KEY: entry.data[CONF_API_KEY]},
            options={
                CONF_SHOW_ON_MAP: show_on_map_by_api_key.get(api_key, False),
            },
            version=SCHEMA_VERSION,
        )

    for api_key, (parent_entry, _) in api_key_entries.items():
        if parent_entry.version > SCHEMA_VERSION:
            continue

        desired_options = {
            CONF_SHOW_ON_MAP: show_on_map_by_api_key.get(api_key, False),
        }

        if parent_entry.version == SCHEMA_VERSION:
            if (
                parent_entry.options.get(CONF_SHOW_ON_MAP, False)
                != desired_options[CONF_SHOW_ON_MAP]
            ):
                # Align options across siblings already on schema v2
                hass.config_entries.async_update_entry(
                    parent_entry,
                    options=desired_options,
                )
            continue

        if parent_entry.version == 1 and parent_entry.disabled_by is None:
            # Enabled entries are migrated by async_migrate_entry
            continue


async def async_migrate_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Migrate config entry."""
    if entry.version == SCHEMA_VERSION:
        return True

    if entry.version != 1:
        LOGGER.error("Unsupported schema version %s", entry.version)
        return False

    LOGGER.info("Migrating schema version from %s to %s", entry.version, SCHEMA_VERSION)

    # v1 schema:
    #   Sensor indices in options as a list of integers, duplicates are allowed and
    #   will not be removed during migration
    #   API key in data as a string, no duplicate API keys allowed
    CONF_SENSOR_INDICES: Final[str] = "sensor_indices"

    # v2 schema:
    #   One or more config subentries, each subentry has a single sensor index,
    #   no duplicate sensors allowed
    #   API key in data as a string, no duplicate API keys allowed

    index_list: list[int] | None = entry.options.get(CONF_SENSOR_INDICES)

    if not index_list or len(index_list) == 0:
        LOGGER.warning("No sensors registered in configuration")
        return hass.config_entries.async_update_entry(
            entry,
            version=SCHEMA_VERSION,
        )

    dev_reg = dr.async_get(hass)
    dev_list = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in dev_list:
        identifiers = (
            int(identifier[1])
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        )
        sensor_index = next(identifiers, None)

        if sensor_index is None:
            LOGGER.warning("Device %s is missing a PurpleAir identifier", device.id)
            continue

        if sensor_index not in index_list:
            LOGGER.warning(
                "Device %s sensor index %s not found in options; skipping",
                device.id,
                sensor_index,
            )
            continue

        # Remove the old entry and then re-add as a subentry
        dev_reg.async_remove_device(device.id)

        # Keep subentry logic in sync with config_flow.py:async_step_select_sensor()
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_SENSOR_INDEX: sensor_index}),
                subentry_type=CONF_SENSOR,
                title=f"{device.name} ({sensor_index})",
                unique_id=str(sensor_index),
            ),
        )

    # Keep entry logic in sync with config_flow.py:async_step_api_key()
    title: str = TITLE
    config_list = hass.config_entries.async_entries(
        domain=DOMAIN, include_disabled=True, include_ignore=True
    )
    if len(config_list) > 1:
        title = f"{TITLE} ({entry.title})"

    return hass.config_entries.async_update_entry(
        entry,
        title=title,
        unique_id=entry.data[CONF_API_KEY],
        data={CONF_API_KEY: entry.data[CONF_API_KEY]},
        options={CONF_SHOW_ON_MAP: entry.options.get(CONF_SHOW_ON_MAP, False)},
        version=SCHEMA_VERSION,
    )


async def async_reload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
