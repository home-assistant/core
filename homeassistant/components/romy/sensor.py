"""Sensor checking adc and status values from your ROMY."""

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RomyVacuumCoordinator
from .entity import RomyEntity

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rssi",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="dustbin_sensor",
        translation_key="dustbin_sensor",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="total_number_of_cleaning_runs",
        translation_key="total_number_of_cleaning_runs",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="runs",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="total_area_cleaned",
        translation_key="total_area_cleaned",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=AREA_SQUARE_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="total_distance_driven",
        translation_key="total_distance_driven",
        state_class=SensorStateClass.TOTAL,
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
        RomySensor(coordinator, entity_description)
        for entity_description in SENSORS
        if entity_description.key in coordinator.romy.sensors
    )


class RomySensor(RomyEntity, SensorEntity):
    """RomySensor Class."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize ROMYs StatusSensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entity_description.key}_{self.romy.unique_id}"
        self.entity_description = entity_description

    @property
    def native_value(self) -> int:
        """Return the value of the sensor."""
        value: int = self.romy.sensors[self.entity_description.key]
        return value
