"""Creates HomeWizard Number entities."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data.state:
        async_add_entities([HWEnergyNumberEntity(coordinator, entry)])


class HWEnergyNumberEntity(HomeWizardEntity, NumberEntity):
    """Representation of status light number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lightbulb-on"
    _attr_name = "Status light brightness"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the control number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_status_light_brightness"

    @homewizard_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.api.state_set(brightness=int(value * (255 / 100)))
        await self.coordinator.async_refresh()

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if (
            self.coordinator.data.state is None
            or self.coordinator.data.state.brightness is None
        ):
            return None
        return round(self.coordinator.data.state.brightness * (100 / 255))
