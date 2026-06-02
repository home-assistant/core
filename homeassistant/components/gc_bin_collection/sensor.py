"""Sensor platform for Gold Coast Bin Collection."""

import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GCBinCollectionConfigEntry, GCBinCollectionCoordinator

PARALLEL_UPDATES = 1
SCAN_INTERVAL = datetime.timedelta(hours=12)

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="landfill",
        translation_key="landfill",
    ),
    SensorEntityDescription(
        key="recycling",
        translation_key="recycling",
    ),
    SensorEntityDescription(
        key="organics",
        translation_key="organics",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GCBinCollectionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gold Coast Bin Collection sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GCBinCollectionSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class GCBinCollectionSensor(
    CoordinatorEntity[GCBinCollectionCoordinator], SensorEntity
):
    """Representation of a Gold Coast Bin Collection sensor."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GCBinCollectionCoordinator,
        entry: GCBinCollectionConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime.date | None:
        """Return the next collection date for this bin type."""
        return self.coordinator.data.get(self.entity_description.key)
