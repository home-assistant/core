"""Support for Proximity sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DIR_OF_TRAVEL, ATTR_DIST_TO, ATTR_NEAREST, DOMAIN
from .coordinator import ProximityDataUpdateCoordinator

SENSORS_PER_ENTITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_DIST_TO,
        name="Distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    SensorEntityDescription(
        key=ATTR_DIR_OF_TRAVEL,
        name="Direction of travel",
        translation_key=ATTR_DIR_OF_TRAVEL,
        icon="mdi:compass-outline",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "arrived",
            "away_from",
            "stationary",
            "towards",
        ],
    ),
]

SENSORS_PER_PROXIMITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_NEAREST,
        name="Nearest",
        translation_key=ATTR_NEAREST,
        icon="mdi:near-me",
    ),
]


def _device_info(coordinator: ProximityDataUpdateCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.config_entry.title,
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the proximity sensors."""

    coordinator: ProximityDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ProximitySensor | ProximityTrackedEntitySensor] = [
        ProximitySensor(description, coordinator)
        for description in SENSORS_PER_PROXIMITY
    ]

    tracked_entity_descriptors = []

    entity_reg = er.async_get(hass)
    for tracked_entity_id in coordinator.tracked_entities:
        if (entity_entry := entity_reg.async_get(tracked_entity_id)) is not None:
            tracked_entity_descriptors.append(
                {
                    "entity_id": tracked_entity_id,
                    "identifier": entity_entry.id,
                }
            )
        else:
            tracked_entity_descriptors.append(
                {
                    "entity_id": tracked_entity_id,
                    "identifier": tracked_entity_id,
                }
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
        tracked_entity_descriptor: dict[str, str],
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.tracked_entity_id = tracked_entity_descriptor["entity_id"]

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{tracked_entity_descriptor['identifier']}_{description.key}"
        self._attr_name = f"{self.tracked_entity_id.split('.')[-1]} {description.name}"
        self._attr_device_info = _device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        """Register entity mapping."""
        await super().async_added_to_hass()
        self.coordinator.async_add_entity_mapping(
            self.tracked_entity_id, self.entity_id
        )

    @property
    def data(self) -> dict[str, str | int | None] | None:
        """Get data from coordinator."""
        return self.coordinator.data.entities.get(self.tracked_entity_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.data is not None

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        if self.data is None:
            return None
        return self.data.get(self.entity_description.key)
