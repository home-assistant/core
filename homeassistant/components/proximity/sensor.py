"""Support for Proximity sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import ATTR_DIR_OF_TRAVEL, ATTR_DIST_TO, ATTR_NEAREST, DOMAIN
from .coordinator import ProximityDataUpdateCoordinator

SENSORS_PER_ENTITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_DIST_TO,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    SensorEntityDescription(
        key=ATTR_DIR_OF_TRAVEL,
        translation_key=ATTR_DIR_OF_TRAVEL,
        icon="mdi:compass-outline",
    ),
]

SENSORS_PER_PROXIMITY: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_NEAREST, translation_key=ATTR_NEAREST, icon="mdi:near-me"
    ),
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Proximity sensor platform."""
    if discovery_info is None:
        return

    coordinator: ProximityDataUpdateCoordinator = hass.data[DOMAIN][
        discovery_info[CONF_NAME]
    ]

    entities: list[ProximitySensor | ProximityTrackedEntitySensor] = [
        ProximitySensor(sensor, coordinator) for sensor in SENSORS_PER_PROXIMITY
    ]

    entities += [
        ProximityTrackedEntitySensor(sensor, coordinator, tracked_entity)
        for sensor in SENSORS_PER_ENTITY
        for tracked_entity in coordinator.proximity_devices
    ]

    async_add_entities(entities)


class ProximitySensor(SensorEntity, CoordinatorEntity[ProximityDataUpdateCoordinator]):
    """Represents a Proximity sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: ProximityDataUpdateCoordinator,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = slugify(
            f"{slugify(coordinator.friendly_name)}_{description.key}"
        )

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        if (
            value := self.coordinator.data.proximity[self.entity_description.key]
        ) == "not set":
            return None
        return value


class ProximityTrackedEntitySensor(
    SensorEntity, CoordinatorEntity[ProximityDataUpdateCoordinator]
):
    """Represents a Proximity tracked entity sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: ProximityDataUpdateCoordinator,
        tracked_entity: str,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.tracked_entity = tracked_entity

        self._attr_unique_id = slugify(
            f"{slugify(coordinator.friendly_name)}_{tracked_entity}_{description.key}"
        )

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        if (data := self.coordinator.data.entities.get(self.tracked_entity)) is None:
            return None
        return data.get(self.entity_description.key)
