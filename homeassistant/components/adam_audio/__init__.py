"""ADAM Audio Home Assistant Integration.

Supports ADAM Audio A-Series studio monitors via AES70/OCA over UDP.
Auto-discovers speakers via mDNS (_oca._udp.local.) and also accepts
manually configured IP addresses as a fallback.

Each physical speaker becomes an HA Device with Switch, Select, and Number
child entities.  A virtual 'All Speakers' group device is automatically
created to control all speakers simultaneously.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER
from .coordinator import AdamAudioCoordinator
from .data import AdamAudioData, AdamAudioIntegrationData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .data import AdamAudioConfigEntry


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the ADAM Audio integration."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = AdamAudioIntegrationData(coordinators={})
    return True


def get_coordinators(hass: HomeAssistant) -> list[AdamAudioCoordinator]:
    """Return all currently loaded ADAM Audio coordinators."""
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

    entry.runtime_data = AdamAudioData(
        client=coordinator.client,
        coordinator=coordinator,
    )

    # Ensure integration-wide state exists (especially for tests)
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


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
) -> None:
    """Reload entry after options update."""
    await hass.config_entries.async_reload(entry.entry_id)
