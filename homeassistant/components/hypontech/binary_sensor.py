"""The binary sensors for Hypontech integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HypontechConfigEntry, HypontechDataCoordinator, HypontechPlant
from .entity import HypontechPlantEntity


def _is_plant_online(plant: HypontechPlant) -> bool | None:
    """Return whether the plant is online."""
    if plant.info.status == "online":
        return True
    if plant.info.status == "offline":
        return False
    return None


@dataclass(frozen=True, kw_only=True)
class HypontechPlantBinarySensorDescription(BinarySensorEntityDescription):
    """Describes Hypontech plant binary sensor entity."""

    is_on_fn: Callable[[HypontechPlant], bool | None]


PLANT_BINARY_SENSORS: tuple[HypontechPlantBinarySensorDescription, ...] = (
    HypontechPlantBinarySensorDescription(
        key="status",
        translation_key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_plant_online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HypontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        HypontechPlantBinarySensor(coordinator, plant_id, desc)
        for plant_id in coordinator.data.plants
        for desc in PLANT_BINARY_SENSORS
    )


class HypontechPlantBinarySensor(HypontechPlantEntity, BinarySensorEntity):
    """Class describing Hypontech plant binary sensor entities."""

    entity_description: HypontechPlantBinarySensorDescription

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        plant_id: str,
        description: HypontechPlantBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, plant_id)
        self.entity_description = description
        self._attr_unique_id = f"{plant_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.plant)
