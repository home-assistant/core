"""Binary sensors for the NexBlue integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_lock",
        translation_key="is_lock",
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="is_disable",
        translation_key="is_disable",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NexBlue binary sensors for every discovered charger."""
    coordinator = entry.runtime_data
    async_add_entities(
        NexBlueBinarySensor(coordinator, serial_number, description)
        for serial_number in coordinator.data
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class NexBlueBinarySensor(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], BinarySensorEntity
):
    """Expose NexBlue charger boolean telemetry."""

    _attr_has_entity_name = True
    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor for one charger metric."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
            serial_number=serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether this charger is currently reachable."""
        return (
            super().available
            and self.coordinator.data.get(self._serial_number) is not None
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        status = self.coordinator.data[self._serial_number]
        assert status is not None
        if self.entity_description.key == "is_disable":
            return not status.is_disable
        return not status.is_lock
