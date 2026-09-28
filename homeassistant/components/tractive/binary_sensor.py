"""Support for Tractive binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_POWER_SAVING
from .coordinator import Trackables, TractiveConfigEntry, TractiveCoordinator
from .entity import TractiveEntity


class TractiveBinarySensor(TractiveEntity, BinarySensorEntity):
    """Tractive sensor."""

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        item: Trackables,
        description: TractiveBinarySensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(
            coordinator,
            item.trackable,
            item.tracker_details,
        )
        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        status = self.coordinator.client.status["trackers"].get(self._tracker_id, {})
        return status.get(self.entity_description.key) is not None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self.coordinator.client.status["trackers"].get(self._tracker_id, {})
        self._attr_is_on = status.get(self.entity_description.key)
        super()._handle_coordinator_update()


@dataclass(frozen=True, kw_only=True)
class TractiveBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Tractive binary sensor entities."""

    supported: Callable[[dict], bool] = lambda _: True


SENSOR_TYPES = [
    TractiveBinarySensorEntityDescription(
        key=ATTR_BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported=lambda details: details.get("charging_state") is not None,
    ),
    TractiveBinarySensorEntityDescription(
        key=ATTR_POWER_SAVING,
        translation_key="tracker_power_saving",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tractive device trackers."""
    coordinator = entry.runtime_data.coordinator
    trackables = entry.runtime_data.trackables

    entities = [
        TractiveBinarySensor(coordinator, item, description)
        for description in SENSOR_TYPES
        for item in trackables
        if description.supported(item.tracker_details)
    ]

    async_add_entities(entities)
