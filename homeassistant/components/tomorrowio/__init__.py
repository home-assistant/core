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
from homeassistant.core import HomeAssistant, callback
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
    entries = hass.config_entries.async_entries(DOMAIN)
    if not any(entry.version == 1 for entry in entries):
        return

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    groups: dict[str, list[TomorrowioConfigEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.data[CONF_API_KEY], []).append(entry)

    for api_key, group in groups.items():
        # Prefer an already-migrated entry (an interrupted earlier run), then
        # an enabled one, as the surviving parent entry.
        parent_entry = min(
            group, key=lambda e: (e.version == 1, e.disabled_by is not None)
        )
        all_disabled = all(e.disabled_by is not None for e in group)

        for entry in group:
            if entry.version != 1:
                continue
            subentry = _async_get_or_create_subentry(hass, parent_entry, entry)
            _async_move_registry_rows(
                device_registry,
                entity_registry,
                entry,
                parent_entry,
                subentry,
                all_disabled,
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


@callback
def _async_get_or_create_subentry(
    hass: HomeAssistant,
    parent_entry: TomorrowioConfigEntry,
    entry: TomorrowioConfigEntry,
) -> ConfigSubentry:
    """Return the location subentry for a v1 entry, creating it if needed.

    An interrupted earlier run may already have persisted the subentry
    without having removed its source entry; reuse it in that case.
    """
    location = entry.data[CONF_LOCATION]
    unique_id = f"{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}"
    if existing := next(
        (
            subentry
            for subentry in parent_entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)
            if subentry.unique_id == unique_id
        ),
        None,
    ):
        return existing
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
        unique_id=unique_id,
    )
    hass.config_entries.async_add_subentry(parent_entry, subentry)
    return subentry


@callback
def _async_move_registry_rows(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: TomorrowioConfigEntry,
    parent_entry: TomorrowioConfigEntry,
    subentry: ConfigSubentry,
    all_disabled: bool,
) -> None:
    """Move a v1 entry's device and entities onto its location subentry.

    The registries reset a CONFIG_ENTRY disabled_by when a row moves onto an
    enabled entry, so it is recomputed manually unless the whole API-key
    group is disabled.
    """
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
