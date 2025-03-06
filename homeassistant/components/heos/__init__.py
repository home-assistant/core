"""Denon HEOS Media Player."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import services
from .const import DOMAIN
from .coordinator import HeosConfigEntry, HeosCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

MIN_UPDATE_SOURCES = timedelta(seconds=1)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HEOS component."""
    services.register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Initialize config entry which represents the HEOS controller."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    # Migrate non-string device identifiers.
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        for ident in device.identifiers:
            if ident[0] != DOMAIN or isinstance(ident[1], str):
                continue

            player_id = int(ident[1])  # type: ignore[unreachable]

            # Create set of identifiers excluding this integration
            identifiers = {ident for ident in device.identifiers if ident[0] != DOMAIN}
            migrated_identifiers = {(DOMAIN, str(player_id))}
            # Add migrated if not already present in another device, which occurs if the user downgraded and then upgraded
            if not device_registry.async_get_device(migrated_identifiers):
                identifiers.update(migrated_identifiers)
            if len(identifiers) > 0:
                device_registry.async_update_device(
                    device.id, new_identifiers=identifiers
                )
            else:
                device_registry.async_remove_device(device.id)
            break

    coordinator = HeosCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HeosConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Remove config entry from device if no longer present."""
    return not any(
        (domain, key)
        for domain, key in device.identifiers
        if domain == DOMAIN and int(key) in entry.runtime_data.heos.players
    )
