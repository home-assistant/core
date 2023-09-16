"""The Flipr integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, CONF_FLIPR_ID, DOMAIN, MANUFACTURER
from .coordinator import FliprDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flipr from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = FliprDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FliprEntity(CoordinatorEntity):
    """Implements a common class elements representing the Flipr component."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize Flipr sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.config_entry:
            flipr_id = coordinator.config_entry.data[CONF_FLIPR_ID]
            self._attr_unique_id = f"{flipr_id}-{description.key}"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, flipr_id)},
                manufacturer=MANUFACTURER,
                name=f"Flipr {flipr_id}",
            )
