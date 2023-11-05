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

SENSORS: list[SensorEntityDescription] = [
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

    coordinator = hass.data[DOMAIN][discovery_info[CONF_NAME]]

    async_add_entities(ProximitySensor(sensor, coordinator) for sensor in SENSORS)


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
    def native_value(self) -> str | int | float | None:
        """Return native sensor value."""
        if (value := self.coordinator.data[self.entity_description.key]) == "not set":
            return None
        return value
