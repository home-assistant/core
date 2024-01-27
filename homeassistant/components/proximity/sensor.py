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
        ProximitySensor(description, coordinator)
        for description in SENSORS_PER_PROXIMITY
    ]

    entities += [
        ProximityTrackedEntitySensor(description, coordinator, tracked_entity_id)
        for description in SENSORS_PER_ENTITY
        for tracked_entity_id in coordinator.tracked_entities
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

        # entity name will be removed as soon as we have a config entry
        # and can follow the entity naming guidelines
        self._attr_name = f"{coordinator.friendly_name} {description.name}"

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
        tracked_entity_id: str,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.tracked_entity_id = tracked_entity_id

        # entity name will be removed as soon as we have a config entry
        # and can follow the entity naming guidelines
        self._attr_name = (
            f"{coordinator.friendly_name} {tracked_entity_id} {description.name}"
        )

    @property
    def native_value(self) -> str | float | None:
        """Return native sensor value."""
        if (data := self.coordinator.data.entities.get(self.tracked_entity_id)) is None:
            return None
        return data.get(self.entity_description.key)
