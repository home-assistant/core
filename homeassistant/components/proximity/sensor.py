"""Support for Proximity sensors."""

from __future__ import annotations

from typing import NamedTuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_TO,
    ATTR_NEAREST,
    ATTR_NEAREST_DIR_OF_TRAVEL,
    ATTR_NEAREST_DIST_TO,
    DOMAIN,
)
from .coordinator import ProximityConfigEntry, ProximityDataUpdateCoordinator

DIRECTIONS = ["arrived", "away_from", "stationary", "towards"]

SENSORS_PER_ENTITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_DIST_TO,
        translation_key=ATTR_DIST_TO,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    SensorEntityDescription(
        key=ATTR_DIR_OF_TRAVEL,
        translation_key=ATTR_DIR_OF_TRAVEL,
        device_class=SensorDeviceClass.ENUM,
        options=DIRECTIONS,
    ),
]

SENSORS_PER_PROXIMITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_NEAREST,
        translation_key=ATTR_NEAREST,
    ),
    SensorEntityDescription(
        key=ATTR_DIST_TO,
        translation_key=ATTR_NEAREST_DIST_TO,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    SensorEntityDescription(
        key=ATTR_DIR_OF_TRAVEL,
        translation_key=ATTR_NEAREST_DIR_OF_TRAVEL,
        device_class=SensorDeviceClass.ENUM,
        options=DIRECTIONS,
    ),
]


class TrackedEntityDescriptor(NamedTuple):
    """Descriptor of a tracked entity."""

    entity_id: str
    identifier: str
    name: str


def _device_info(coordinator: ProximityDataUpdateCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.config_entry.title,
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProximityConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the proximity sensors."""

    coordinator = entry.runtime_data

    entities: list[ProximitySensor | ProximityTrackedEntitySensor] = [
        ProximitySensor(description, coordinator)
        for description in SENSORS_PER_PROXIMITY
    ]

    tracked_entity_descriptors: list[TrackedEntityDescriptor] = []

    entity_reg = er.async_get(hass)
    for tracked_entity_id in coordinator.tracked_entities:
        tracked_entity_object_id = tracked_entity_id.split(".")[-1]
        if (entity_entry := entity_reg.async_get(tracked_entity_id)) is not None:
            tracked_entity_descriptors.append(
                TrackedEntityDescriptor(
                    tracked_entity_id,
                    entity_entry.id,
                    entity_entry.name
                    or entity_entry.original_name
                    or tracked_entity_object_id,
                )
            )
        else:
            tracked_entity_descriptors.append(
                TrackedEntityDescriptor(
                    tracked_entity_id,
                    tracked_entity_id,
                    tracked_entity_object_id,
                )
            )

    entities += [
        ProximityTrackedEntitySensor(
            description, coordinator, tracked_entity_descriptor
        )
        for description in SENSORS_PER_ENTITY
        for tracked_entity_descriptor in tracked_entity_descriptors
    ]

    async_add_entities(entities)


class ProximitySensor(CoordinatorEntity[ProximityDataUpdateCoordinator], SensorEntity):
    """Represents a Proximity sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: ProximityDataUpdateCoordinator,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        if (
            value := self.coordinator.data.proximity[self.entity_description.key]
        ) == "not set":
            return None
        return value


class ProximityTrackedEntitySensor(
    CoordinatorEntity[ProximityDataUpdateCoordinator], SensorEntity
):
    """Represents a Proximity tracked entity sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: ProximityDataUpdateCoordinator,
        tracked_entity_descriptor: TrackedEntityDescriptor,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.tracked_entity_id = tracked_entity_descriptor.entity_id

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{tracked_entity_descriptor.identifier}_{description.key}"
        self._attr_device_info = _device_info(coordinator)
        self._attr_translation_placeholders = {
            "tracked_entity": tracked_entity_descriptor.name
        }

    async def async_added_to_hass(self) -> None:
        """Register entity mapping."""
        await super().async_added_to_hass()
        self.coordinator.async_add_entity_mapping(
            self.tracked_entity_id, self.entity_id
        )

    @property
    def data(self) -> dict[str, str | int | None]:
        """Get data from coordinator."""
        return self.coordinator.data.entities[self.tracked_entity_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.tracked_entity_id in self.coordinator.data.entities
        )

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        return self.data.get(self.entity_description.key)
