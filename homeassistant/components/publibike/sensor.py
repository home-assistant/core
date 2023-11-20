"""Support for PubliBike Public API for bike sharing in Switzerland."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PubliBikeDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class PubliBikeSensorEntityDescription(SensorEntityDescription):
    """Describes a PubliBike's Bike sensor entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PubliBike sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[Entity] = [
        BikeSensor(
            coordinator,
            PubliBikeSensorEntityDescription(
                key="bike_sensor", translation_key="bike_sensor"
            ),
            config_entry.entry_id,
        ),
        EBikeSensor(
            coordinator,
            PubliBikeSensorEntityDescription(
                key="ebike_sensor", translation_key="ebike_sensor"
            ),
            config_entry.entry_id,
        ),
    ]
    async_add_entities(entities)


class PubliBikeSensor(CoordinatorEntity[PubliBikeDataUpdateCoordinator], SensorEntity):
    """Representation of a PubliBike sensor."""

    entity_description: PubliBikeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PubliBikeDataUpdateCoordinator,
        description: PubliBikeSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._attr_device_info = DeviceInfo(
            name=coordinator.station.name,
            identifiers={(DOMAIN, coordinator.station.stationId)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{entry_id}_{description.key}"


class EBikeSensor(PubliBikeSensor):
    """Representation of an E-Bike Sensor."""

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.available_ebikes

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"All E-bikes": len(self.coordinator.station.ebikes)}


class BikeSensor(PubliBikeSensor):
    """Representation of a Bike Sensor."""

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self.coordinator.station.bikes)
