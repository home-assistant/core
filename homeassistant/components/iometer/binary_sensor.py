"""IOmeter binary sensor."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IOMeterCoordinator, IOmeterData
from .entity import IOmeterEntity


@dataclass(frozen=True, kw_only=True)
class IOmeterBinarySensorDescription(BinarySensorEntityDescription):
    """Describes Iometer binary sensor entity."""

    value_fn: Callable[[IOmeterData], bool | None]


SENSOR_TYPES: list[IOmeterBinarySensorDescription] = [
    IOmeterBinarySensorDescription(
        key="connection_status",
        translation_key="connection_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.status.device.core.connection_status == "connected"
            if data.status.device.core.connection_status is not None
            else None
        ),
    ),
    IOmeterBinarySensorDescription(
        key="attachment_status",
        translation_key="attachment_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.status.device.core.attachment_status == "attached"
            if data.status.device.core.attachment_status is not None
            else None
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sensors."""
    coordinator: IOMeterCoordinator = config_entry.runtime_data

    async_add_entities(
        IOmeterBinarySensor(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSOR_TYPES
    )


class IOmeterBinarySensor(IOmeterEntity, BinarySensorEntity):
    """Defines a IOmeter binary sensor."""

    entity_description: IOmeterBinarySensorDescription

    def __init__(
        self,
        coordinator: IOMeterCoordinator,
        description: IOmeterBinarySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.identifier}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
