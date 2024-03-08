"""Sensor checking adc and status values from your ROMY."""

from dataclasses import dataclass

from romy import RomyRobot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RomyVacuumCoordinator


@dataclass(frozen=True)
class RomySensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing Romy data."""


SENSORS: list[RomySensorEntityDescription] = [
    RomySensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="dustbin_sensor",
        translation_key="dustbin_sensor",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="total_number_of_cleaning_runs",
        translation_key="total_number_of_cleaning_runs",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Cleaning Runs",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="total_area_cleaned",
        translation_key="total_area_cleaned",
        native_unit_of_measurement=AREA_SQUARE_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RomySensorEntityDescription(
        key="total_distance_driven",
        translation_key="total_distance_driven",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        RomySensor(coordinator, coordinator.romy, entity_description)
        for entity_description in SENSORS
        if entity_description.key in coordinator.romy.sensors
    )


class RomySensor(CoordinatorEntity[RomyVacuumCoordinator], SensorEntity):
    """RomySensor Class."""

    entity_description: RomySensorEntityDescription

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        entity_description: RomySensorEntityDescription,
    ) -> None:
        """Initialize ROMYs StatusSensor."""
        self._sensor_value: int | None = None
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )
        self.entity_description = entity_description

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self.entity_description.key}_{self._attr_unique_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sensor_value = self.romy.sensors[self.entity_description.key]
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        return self._sensor_value
