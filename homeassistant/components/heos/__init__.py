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
        for domain, player_id in device.identifiers:
            if domain == DOMAIN and not isinstance(player_id, str):
                device_registry.async_update_device(  # type: ignore[unreachable]
                    device.id, new_identifiers={(DOMAIN, str(player_id))}
                )
            break

    coordinator = HeosCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
