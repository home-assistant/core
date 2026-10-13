"""The binary sensors for Hypontech integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HypontechConfigEntry, HypontechDataCoordinator
from .entity import HypontechPlantEntity

PLANT_STATUS_BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)


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

    entity_description: BinarySensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        plant_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, plant_id)
        self.entity_description = PLANT_STATUS_BINARY_SENSOR_DESCRIPTION
        self._attr_unique_id = f"{plant_id}_{self.entity_description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.plant.info.status == "online"
