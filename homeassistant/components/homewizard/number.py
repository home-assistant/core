"""Creates HomeWizard Number entities."""
from __future__ import annotations

from typing import Optional, cast

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data["state"]:
        async_add_entities(
            [
                HWEnergyNumberEntity(coordinator, entry),
            ]
        )


class HWEnergyNumberEntity(
    CoordinatorEntity[HWEnergyDeviceUpdateCoordinator], NumberEntity
):
    """Representation of status light number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the control number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_status_light_brightness"
        self._attr_name = "Status light brightness"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:lightbulb-on"
        self._attr_device_info = coordinator.device_info

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.api.state_set(brightness=value * (255 / 100))
        await self.coordinator.async_refresh()

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        brightness = cast(Optional[float], self.coordinator.data["state"].brightness)
        if brightness is None:
            return None
        return round(brightness * (100 / 255))
