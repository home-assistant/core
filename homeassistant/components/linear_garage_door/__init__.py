"""The Linear Garage Door integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinearUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Linear Garage Door from a config entry."""

    coordinator = LinearUpdateCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class LinearEntity(CoordinatorEntity[LinearUpdateCoordinator]):
    """Common base for Linear entities."""

    coordinator: LinearUpdateCoordinator
    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        device_name: str,
        subdevice: str,
        config_entry: ConfigEntry,
        coordinator: LinearUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{device_id}-{subdevice}"
        self._config_entry = config_entry
        self._device_id = device_id
        self._device_name = device_name
        self._subdevice = subdevice
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Linear",
            "model": "Garage Door Opener",
        }
