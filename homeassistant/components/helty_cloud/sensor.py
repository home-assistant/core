"""Sensor platform for the Helty Flow Cloud integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyheltycloud import HeltyState

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
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HeltyCloudConfigEntry, HeltyCloudDataUpdateCoordinator
from .entity import HeltyCloudEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HeltyCloudSensorEntityDescription(SensorEntityDescription):
    """Describes a Helty Flow Cloud sensor."""

    value_fn: Callable[[HeltyState], float | None]


SENSORS: tuple[HeltyCloudSensorEntityDescription, ...] = (
    HeltyCloudSensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.temperature_indoor,
    ),
    HeltyCloudSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.temperature_outdoor,
    ),
    HeltyCloudSensorEntityDescription(
        key="indoor_humidity",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.humidity,
    ),
    # The machine ages the filter by the air it moves, not by hours of use.
    HeltyCloudSensorEntityDescription(
        key="filter_volume",
        translation_key="filter_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.filter_partial_m3,
    ),
    HeltyCloudSensorEntityDescription(
        key="total_volume",
        translation_key="total_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.filter_total_m3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeltyCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of every VMC on the account."""
    async_add_entities(
        HeltyCloudSensor(coordinator, description)
        for coordinator in entry.runtime_data
        for description in SENSORS
    )


class HeltyCloudSensor(HeltyCloudEntity, SensorEntity):
    """A reading reported by the ventilation unit."""

    entity_description: HeltyCloudSensorEntityDescription

    def __init__(
        self,
        coordinator: HeltyCloudDataUpdateCoordinator,
        description: HeltyCloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.serial_number}_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current reading."""
        return self.entity_description.value_fn(self.coordinator.data)
