"""Support for Traccar server sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pytraccar import DeviceModel, GeofenceModel, PositionModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import TraccarServerCoordinator
from .entity import TraccarServerEntity


@dataclass(frozen=True, kw_only=True)
class TraccarServerSensorEntityDescription[_T](SensorEntityDescription):
    """Describe Traccar Server sensor entity."""

    data_key: Literal["position", "device", "geofence", "attributes"]
    entity_registry_enabled_default = False
    entity_category = EntityCategory.DIAGNOSTIC
    value_fn: Callable[[_T], StateType]


TRACCAR_SERVER_SENSOR_ENTITY_DESCRIPTIONS: tuple[
    TraccarServerSensorEntityDescription[Any], ...
] = (
    TraccarServerSensorEntityDescription[PositionModel](
        key="attributes.batteryLevel",
        data_key="position",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda x: x["attributes"].get("batteryLevel"),
    ),
    TraccarServerSensorEntityDescription[PositionModel](
        key="speed",
        data_key="position",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        suggested_display_precision=0,
        value_fn=lambda x: x["speed"],
    ),
    TraccarServerSensorEntityDescription[PositionModel](
        key="altitude",
        data_key="position",
        translation_key="altitude",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=1,
        value_fn=lambda x: x["altitude"],
    ),
    TraccarServerSensorEntityDescription[PositionModel](
        key="address",
        data_key="position",
        translation_key="address",
        value_fn=lambda x: x["address"],
    ),
    TraccarServerSensorEntityDescription[GeofenceModel | None](
        key="name",
        data_key="geofence",
        translation_key="geofence",
        value_fn=lambda x: x["name"] if x else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: TraccarServerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TraccarServerSensor(
            coordinator=coordinator,
            device=entry["device"],
            description=description,
        )
        for entry in coordinator.data.values()
        for description in TRACCAR_SERVER_SENSOR_ENTITY_DESCRIPTIONS
    )


class TraccarServerSensor[_T](TraccarServerEntity, SensorEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    entity_description: TraccarServerSensorEntityDescription[_T]

    def __init__(
        self,
        coordinator: TraccarServerCoordinator,
        device: DeviceModel,
        description: TraccarServerSensorEntityDescription[_T],
    ) -> None:
        """Initialize the Traccar Server sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = (
            f"{device['uniqueId']}_{description.data_key}_{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(
            getattr(self, f"traccar_{self.entity_description.data_key}")
        )
