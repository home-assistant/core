"""The Steam integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SteamDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Steam integration."""
    if DOMAIN in config:
        async_create_issue(
            hass,
            DOMAIN,
            "removed_yaml",
            breaks_in_ha_version="2022.8.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="removed_yaml",
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Steam from a config entry."""
    coordinator = SteamDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SteamEntity(CoordinatorEntity[SteamDataUpdateCoordinator]):
    """Representation of a Steam entity."""

    _attr_attribution = "Data provided by Steam"

    def __init__(self, coordinator: SteamDataUpdateCoordinator) -> None:
        """Initialize a Steam entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://store.steampowered.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )
