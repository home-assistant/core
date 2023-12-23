"""Life360 integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_OPTIONS, DOMAIN
from .coordinator import Life360DataUpdateCoordinator, MissingLocReason

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class IntegData:
    """Integration data."""

    cfg_options: dict[str, Any] | None = None
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

    def __post_init__(self):
        """Finish initialization of cfg_options."""
        self.cfg_options = self.cfg_options or {}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    hass.data.setdefault(DOMAIN, IntegData(config.get(DOMAIN)))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    hass.data.setdefault(DOMAIN, IntegData())

    # Check if this entry was created when this was a "legacy" tracker. If it was,
    # update with missing data.
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=entry.data[CONF_USERNAME].lower(),
            options=DEFAULT_OPTIONS | hass.data[DOMAIN].cfg_options,
        )

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
