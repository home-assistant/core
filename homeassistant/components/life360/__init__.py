"""Life360 integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import Life360DataUpdateCoordinator, MissingLocReason

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.BUTTON]


@dataclass
class IntegData:
    """Integration data."""

    # ConfigEntry.entry_id: Life360DataUpdateCoordinator
    coordinators: dict[str, Life360DataUpdateCoordinator] = field(
        init=False, default_factory=dict
    )
    # member_id: missing location reason
    missing_loc_reason: dict[str, MissingLocReason] = field(
        init=False, default_factory=dict
    )
    # member_id: ConfigEntry.entry_id
    tracked_members: dict[str, str] = field(init=False, default_factory=dict)
    logged_circles: list[str] = field(init=False, default_factory=list)
    logged_places: list[str] = field(init=False, default_factory=list)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    hass.data.setdefault(DOMAIN, IntegData())

    coordinator = Life360DataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN].coordinators[entry.entry_id] = coordinator

    # Set up components for our platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    # Unload components for our platforms.
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN].coordinators[entry.entry_id]
        # Remove any members that were tracked by this entry.
        for member_id, entry_id in hass.data[DOMAIN].tracked_members.copy().items():
            if entry_id == entry.entry_id:
                del hass.data[DOMAIN].tracked_members[member_id]

    return unload_ok
