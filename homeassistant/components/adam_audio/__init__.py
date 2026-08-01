"""ADAM Audio Home Assistant Integration.

Supports ADAM Audio A-Series studio monitors via AES70/OCA over UDP.
Auto-discovers speakers via mDNS (_oca._udp.local.) and also accepts
manually configured IP addresses as a fallback.

Each physical speaker becomes an HA Device with Switch, Select, and Number
child entities.  A virtual 'All Speakers' group device is automatically
created to control all speakers simultaneously.
"""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SERIAL, DOMAIN, LOGGER
from .coordinator import AdamAudioCoordinator
from .data import AdamAudioConfigEntry, AdamAudioData, AdamAudioIntegrationData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the ADAM Audio integration."""
    # Tracks group entities across ALL config entries (one per speaker), so it
    # can't live on a single entry's runtime_data.
    if DOMAIN not in hass.data:
        # pylint: disable-next=home-assistant-use-runtime-data
        hass.data[DOMAIN] = AdamAudioIntegrationData(coordinators={})
    return True


def get_integration_data(hass: HomeAssistant) -> AdamAudioIntegrationData:
    """Return this integration's cross-entry state.

    Tracks group entities across ALL config entries (one per speaker), so it
    can't live on a single entry's runtime_data. Only valid once
    async_setup_entry has run for at least one entry.
    """
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN]


def get_coordinators(hass: HomeAssistant) -> list[AdamAudioCoordinator]:
    """Return all currently loaded ADAM Audio coordinators."""
    # pylint: disable-next=home-assistant-use-runtime-data
    data: AdamAudioIntegrationData | None = hass.data.get(DOMAIN)
    if not data:
        return []
    return list(data.coordinators.values())


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
) -> bool:
    """Set up ADAM Audio from a config entry (one entry = one physical speaker)."""
    coordinator = AdamAudioCoordinator(hass, entry)
    await coordinator.async_setup()  # raises ConfigEntryNotReady if unreachable

    _async_migrate_device_identifiers(hass, coordinator)
    _async_migrate_entry_unique_id(hass, entry, coordinator)
    _async_migrate_entity_unique_ids(hass, entry, coordinator)

    entry.runtime_data = AdamAudioData(
        client=coordinator.client,
        coordinator=coordinator,
    )

    # Ensure integration-wide state exists (especially for tests). Tracks group
    # entities across ALL config entries, so it can't live on runtime_data.
    # pylint: disable-next=home-assistant-use-runtime-data
    integration_data = hass.data.setdefault(
        DOMAIN, AdamAudioIntegrationData(coordinators={})
    )
    integration_data.coordinators[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-run setup if the entry's options are updated (e.g., host changed).
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
) -> bool:
    """Unload a config entry cleanly."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Integration data might missing if async_setup was skipped (e.g. tests)
        integration_data: AdamAudioIntegrationData | None = hass.data.get(DOMAIN)
        if integration_data:
            coordinator = integration_data.coordinators.pop(entry.entry_id, None)
            if coordinator:
                await coordinator.async_shutdown()

            # The group entities live under the platforms of the entry that
            # created them, so they were just removed along with this entry.
            # Reset the flags so the next entry setup recreates them (this
            # entry reloading, or a remaining entry we schedule below).
            if integration_data.group_owner_entry_id == entry.entry_id:
                integration_data.group_owner_entry_id = None
                integration_data.group_switches_added = False
                integration_data.group_numbers_added = False
                integration_data.group_selects_added = False
                if integration_data.coordinators and not hass.is_stopping:
                    hass.config_entries.async_schedule_reload(
                        next(iter(integration_data.coordinators))
                    )

            LOGGER.debug(
                "Unloaded entry %s; %d coordinators remaining",
                entry.entry_id,
                len(integration_data.coordinators),
            )
        else:
            LOGGER.debug("Skipping coordinator cleanup (domain data missing)")

    return unload_ok


def _async_migrate_device_identifiers(
    hass: HomeAssistant, coordinator: AdamAudioCoordinator
) -> None:
    """Move a device registered under its hardware name to its serial number.

    Versions up to 0.3.x identified devices by hardware name.  Updating the
    existing registry entry in place preserves the device id, so automations
    and dashboards referencing the device keep working.
    """
    if not coordinator.device_serial:
        return
    device_registry = dr.async_get(hass)
    new_identifier = (DOMAIN, coordinator.device_serial)
    if device_registry.async_get_device(identifiers={new_identifier}):
        return  # already migrated (or fresh install)
    old_device = device_registry.async_get_device(
        identifiers={(DOMAIN, coordinator.device_unique_id)}
    )
    if old_device:
        device_registry.async_update_device(
            old_device.id, new_identifiers={new_identifier}
        )
        LOGGER.debug(
            "Migrated device %s identifiers to serial %s",
            coordinator.device_unique_id,
            coordinator.device_serial,
        )


def _async_migrate_entry_unique_id(
    hass: HomeAssistant, entry: AdamAudioConfigEntry, coordinator: AdamAudioCoordinator
) -> None:
    """Point this entry's own unique_id at the device serial number.

    Versions up to 0.3.x set the config entry's unique_id to the hardware
    name (e.g. "ASeries-414725") because the serial wasn't fetched yet at
    flow time.  A later zeroconf rediscovery of that same physical speaker
    now computes a serial-based unique_id, so
    _abort_if_unique_id_configured no longer recognizes the device as
    already configured and a duplicate entry gets created — its entities
    then collide with the original entry's (same device_name, same
    unique_id suffix). Migrating the entry's unique_id to the serial closes
    that gap for future rediscoveries.
    """
    if not coordinator.device_serial or entry.unique_id == coordinator.device_serial:
        return
    existing = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, coordinator.device_serial
    )
    if existing and existing.entry_id != entry.entry_id:
        LOGGER.warning(
            "Entry %s (%s) was not migrated to unique_id %s: entry %s already "
            "uses it. This usually means a duplicate entry exists for the same "
            "speaker — remove one of them in Settings > Devices & Services",
            entry.entry_id,
            coordinator.device_description,
            coordinator.device_serial,
            existing.entry_id,
        )
        return
    old_unique_id = entry.unique_id
    hass.config_entries.async_update_entry(
        entry,
        unique_id=coordinator.device_serial,
        data={**entry.data, CONF_SERIAL: coordinator.device_serial},
    )
    LOGGER.debug(
        "Migrated entry %s unique_id from %s to serial %s",
        entry.entry_id,
        old_unique_id,
        coordinator.device_serial,
    )


def _async_migrate_entity_unique_ids(
    hass: HomeAssistant, entry: AdamAudioConfigEntry, coordinator: AdamAudioCoordinator
) -> None:
    """Rename this entry's entities from the hardware-name unique_id to the serial.

    Versions up to 0.3.x built entity unique_ids from the hardware name
    (see AdamAudioCoordinator.entity_unique_id_base); entities now build
    theirs from the serial once it's known. Without this, existing
    registry entries keep the old unique_id — which nothing provides
    anymore, so they go unavailable — while a duplicate set of entities is
    created under the new unique_id. Renaming the existing entries in
    place keeps their entity_id (and history) intact.
    """
    if (
        not coordinator.device_serial
        or coordinator.device_serial == coordinator.device_unique_id
    ):
        return
    old_prefix = f"{DOMAIN}_{coordinator.device_unique_id}_"
    new_prefix = f"{DOMAIN}_{coordinator.device_serial}_"
    entity_registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if not reg_entry.unique_id.startswith(old_prefix):
            continue
        new_unique_id = new_prefix + reg_entry.unique_id[len(old_prefix) :]
        if entity_registry.async_get_entity_id(reg_entry.domain, DOMAIN, new_unique_id):
            LOGGER.warning(
                "Entity %s was not migrated to unique_id %s: already in use",
                reg_entry.entity_id,
                new_unique_id,
            )
            continue
        entity_registry.async_update_entity(
            reg_entry.entity_id, new_unique_id=new_unique_id
        )
        LOGGER.debug(
            "Migrated entity %s unique_id from %s to %s",
            reg_entry.entity_id,
            reg_entry.unique_id,
            new_unique_id,
        )


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
) -> None:
    """Reload entry after options update."""
    await hass.config_entries.async_reload(entry.entry_id)
