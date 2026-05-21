"""Support for hydrological data from the Fed. Office for the Environment."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_DISCHARGE, SENSOR_LEVEL, SENSOR_TEMPERATURE
from .coordinator import SwissHydrologicalDataCoordinator

if TYPE_CHECKING:
    from . import SwissHydroConfigEntry

PARALLEL_UPDATES = 0

ATTR_MAX_24H = "max_24h"
ATTR_MEAN_24H = "mean_24h"
ATTR_MIN_24H = "min_24h"
ATTR_STATION_UPDATE = "station_update"
ATTR_WATER_BODY_TYPE = "water_body_type"


@dataclass(frozen=True, kw_only=True)
class SwissHydroSensorEntityDescription(SensorEntityDescription):
    """Describes a Swiss Hydrological Data sensor entity."""

    condition: str


SENSORS: tuple[SwissHydroSensorEntityDescription, ...] = (
    SwissHydroSensorEntityDescription(
        key=SENSOR_DISCHARGE,
        translation_key=SENSOR_DISCHARGE,
        condition=SENSOR_DISCHARGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SwissHydroSensorEntityDescription(
        key=SENSOR_LEVEL,
        translation_key=SENSOR_LEVEL,
        condition=SENSOR_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SwissHydroSensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        translation_key=SENSOR_TEMPERATURE,
        condition=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwissHydroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Swiss Hydrological Data sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SwissHydrologicalDataSensor(coordinator, description, entry)
        for description in SENSORS
        if description.condition in coordinator.data.get("parameters", {})
    )


class SwissHydrologicalDataSensor(
    CoordinatorEntity[SwissHydrologicalDataCoordinator], SensorEntity
):
    """Representation of a Swiss Hydrological Data sensor."""

    entity_description: SwissHydroSensorEntityDescription
    _attr_attribution = (
        "Data provided by the Swiss Federal Office for the Environment FOEN"
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SwissHydrologicalDataCoordinator,
        description: SwissHydroSensorEntityDescription,
        entry: SwissHydroConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Swiss Federal Office for the Environment FOEN",
        )

    def _get_condition_data(self) -> dict[str, Any]:
        """Return data for this sensor's condition."""
        return self.coordinator.data.get("parameters", {}).get(
            self.entity_description.condition, {}
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._get_condition_data().get("unit")

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self._get_condition_data().get("value")
        if isinstance(value, (int, float)):
            return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        condition_data = self._get_condition_data()
        if not condition_data:
            return {}

        return {
            ATTR_WATER_BODY_TYPE: self.coordinator.data.get("water-body-type"),
            ATTR_STATION_UPDATE: condition_data.get("datetime"),
            ATTR_MAX_24H: condition_data.get("max-24h"),
            ATTR_MEAN_24H: condition_data.get("mean-24h"),
            ATTR_MIN_24H: condition_data.get("min-24h"),
        }
