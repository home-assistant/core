"""Sensor platform for the Vitesy integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aiovitesy.api import VitesyDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import VitesyConfigEntry, VitesyDataUpdateCoordinator
from .entity import VitesyEntity

PARALLEL_UPDATES = 0

# Groups within a measurement payload.
_SENSORS_DATA = "sensors_data"
_STATUS_DATA = "status_data"

# Reading ids within those groups (Shelfy).
_FRIDGE_TEMPERATURE = "TMP01-SY"
_DOOR_OPENINGS = "DOC-SY"
_DOOR_OPEN_DURATION = "DOT-SY"
_BATTERY = "battery"


def _reading(device: VitesyDevice, group: str, reading_id: str) -> float | None:
    """Return a numeric value from a measurement group entry by its id."""
    for entry in device.measurement.get(group, ()):
        if entry.get("id") == reading_id:
            value = entry.get("value")
            return value.get("avg") if isinstance(value, dict) else value
    return None


def _air_quality_score(device: VitesyDevice) -> int | None:
    """Return the air quality score.

    The Hub reports it as a 0-1 fraction; Vitesy's canonical scale is 0-100.
    """
    score = device.measurement.get("score")
    return round(score * 100) if score is not None else None


def _maintenance_due(component: str) -> Callable[[VitesyDevice], datetime | None]:
    """Return a value function for a maintenance component's due date."""

    def _value(device: VitesyDevice) -> datetime | None:
        due_date = device.maintenance.get(component, {}).get("due_date")
        return dt_util.parse_datetime(due_date) if due_date else None

    return _value


@dataclass(frozen=True, kw_only=True)
class VitesySensorEntityDescription(SensorEntityDescription):
    """Describes a Vitesy sensor entity."""

    value_fn: Callable[[VitesyDevice], StateType | datetime]


SENSORS: tuple[VitesySensorEntityDescription, ...] = (
    VitesySensorEntityDescription(
        key="air_quality_score",
        translation_key="air_quality_score",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_air_quality_score,
    ),
    VitesySensorEntityDescription(
        key="fridge_temperature",
        translation_key="fridge_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _FRIDGE_TEMPERATURE),
    ),
    VitesySensorEntityDescription(
        key="door_openings",
        translation_key="door_openings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _DOOR_OPENINGS),
    ),
    VitesySensorEntityDescription(
        key="door_open_duration",
        translation_key="door_open_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _DOOR_OPEN_DURATION),
    ),
    VitesySensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _reading(device, _STATUS_DATA, _BATTERY),
    ),
    VitesySensorEntityDescription(
        key="filter_change_due",
        translation_key="filter_change_due",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_maintenance_due("filter"),
    ),
    VitesySensorEntityDescription(
        key="fridge_cleaning_due",
        translation_key="fridge_cleaning_due",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_maintenance_due("fridge"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitesyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitesy sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitesySensor(coordinator, device_id, description)
        for device_id, device in coordinator.data.items()
        for description in SENSORS
        if description.value_fn(device) is not None
    )


class VitesySensor(VitesyEntity, SensorEntity):
    """Representation of a Vitesy sensor."""

    entity_description: VitesySensorEntityDescription

    def __init__(
        self,
        coordinator: VitesyDataUpdateCoordinator,
        device_id: str,
        description: VitesySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.device)
