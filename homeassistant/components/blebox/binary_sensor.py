"""BleBox binary sensor entities."""

from typing import override

from blebox_uniapi.binary_sensor import BinarySensor as BinarySensorFeature

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BleBoxConfigEntry
from .coordinator import BleBoxCoordinator
from .entity import BleBoxEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="moisture",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="open",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    BinarySensorEntityDescription(
        key="input",
        translation_key="input",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""
    coordinator = config_entry.runtime_data
    entities = [
        BleBoxBinarySensorEntity(coordinator, feature, description)
        for feature in coordinator.box.features.get("binary_sensors", [])
        for description in BINARY_SENSOR_TYPES
        if description.key == feature.device_class
    ]
    async_add_entities(entities)


class BleBoxBinarySensorEntity(BleBoxEntity[BinarySensorFeature], BinarySensorEntity):
    """Representation of a BleBox binary sensor feature."""

    def __init__(
        self,
        coordinator: BleBoxCoordinator,
        feature: BinarySensorFeature,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a BleBox binary sensor feature."""
        super().__init__(coordinator, feature)
        self.entity_description = description
        if feature.name:
            self._attr_name = feature.name

    @property
    @override
    def is_on(self) -> bool:
        """Return the state."""
        return self._feature.state
