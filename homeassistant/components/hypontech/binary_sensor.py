"""The binary sensors for Hypontech integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HypontechConfigEntry, HypontechDataCoordinator
from .entity import HypontechPlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HypontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        HypontechPlantStatusBinarySensor(coordinator, plant_id)
        for plant_id in coordinator.data.plants
    )


class HypontechPlantStatusBinarySensor(HypontechPlantEntity, BinarySensorEntity):
    """Class describing Hypontech plant status binary sensor entity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "status"

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        plant_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, plant_id)
        self._attr_unique_id = f"{plant_id}_status"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.plant.info.status == "online":
            return True
        if self.plant.info.status == "offline":
            return False
        return None
