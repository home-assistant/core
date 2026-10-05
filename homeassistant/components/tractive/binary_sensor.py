"""Support for Tractive binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiotractive import Trackable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_POWER_SAVING
from .coordinator import TractiveConfigEntry, TractiveCoordinator
from .entity import TractiveEntity


class TractiveBinarySensor(TractiveEntity, BinarySensorEntity):
    """Tractive sensor."""

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        trackable: Trackable,
        description: TractiveBinarySensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(coordinator, trackable)
        self._attr_unique_id = f"{trackable.pet_id}_{description.key}"
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        is_on: bool | None = getattr(self._tracker_status, self.entity_description.key)
        return is_on

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.is_on is not None


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
    coordinator = entry.runtime_data

    async_add_entities(
        TractiveBinarySensor(coordinator, trackable, description)
        for description in SENSOR_TYPES
        for trackable in coordinator.trackables
        if description.supported(trackable.tracker_details)
    )
