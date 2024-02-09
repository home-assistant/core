"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from energyflip.const import (
    SOURCE_TYPE_ELECTRICITY,
    SOURCE_TYPE_ELECTRICITY_IN,
    SOURCE_TYPE_ELECTRICITY_IN_LOW,
    SOURCE_TYPE_ELECTRICITY_OUT,
    SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    SOURCE_TYPE_GAS,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    SENSOR_TYPE_RATE,
    SENSOR_TYPE_THIS_DAY,
    SENSOR_TYPE_THIS_MONTH,
    SENSOR_TYPE_THIS_WEEK,
    SENSOR_TYPE_THIS_YEAR,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HuisbaasjeSensorEntityDescription(SensorEntityDescription):
    """Class describing Airly sensor entities."""

    sensor_type: str = SENSOR_TYPE_RATE
    precision: int = 0


SENSORS_INFO = [
    HuisbaasjeSensorEntityDescription(
        translation_key="current_power",
        sensor_type=SENSOR_TYPE_RATE,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key=SOURCE_TYPE_ELECTRICITY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="current_power_peak",
        sensor_type=SENSOR_TYPE_RATE,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key=SOURCE_TYPE_ELECTRICITY_IN,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="current_power_off_peak",
        sensor_type=SENSOR_TYPE_RATE,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key=SOURCE_TYPE_ELECTRICITY_IN_LOW,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="current_power_out_peak",
        sensor_type=SENSOR_TYPE_RATE,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key=SOURCE_TYPE_ELECTRICITY_OUT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="current_power_out_off_peak",
        sensor_type=SENSOR_TYPE_RATE,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key=SOURCE_TYPE_ELECTRICITY_OUT_LOW,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_consumption_peak_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key=SOURCE_TYPE_ELECTRICITY_IN,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_consumption_off_peak_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key=SOURCE_TYPE_ELECTRICITY_IN_LOW,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_production_peak_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key=SOURCE_TYPE_ELECTRICITY_OUT,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_production_off_peak_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key=SOURCE_TYPE_ELECTRICITY_OUT_LOW,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        key=SOURCE_TYPE_ELECTRICITY,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        precision=1,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_week",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        key=SOURCE_TYPE_ELECTRICITY,
        sensor_type=SENSOR_TYPE_THIS_WEEK,
        precision=1,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        key=SOURCE_TYPE_ELECTRICITY,
        sensor_type=SENSOR_TYPE_THIS_MONTH,
        precision=1,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="energy_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        key=SOURCE_TYPE_ELECTRICITY,
        sensor_type=SENSOR_TYPE_THIS_YEAR,
        precision=1,
        icon="mdi:lightning-bolt",
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="current_gas",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        sensor_type=SENSOR_TYPE_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        key=SOURCE_TYPE_GAS,
        icon="mdi:fire",
        precision=1,
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="gas_today",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        key=SOURCE_TYPE_GAS,
        sensor_type=SENSOR_TYPE_THIS_DAY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        precision=1,
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="gas_week",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        key=SOURCE_TYPE_GAS,
        sensor_type=SENSOR_TYPE_THIS_WEEK,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        precision=1,
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="gas_month",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        key=SOURCE_TYPE_GAS,
        sensor_type=SENSOR_TYPE_THIS_MONTH,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        precision=1,
    ),
    HuisbaasjeSensorEntityDescription(
        translation_key="gas_year",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        key=SOURCE_TYPE_GAS,
        sensor_type=SENSOR_TYPE_THIS_YEAR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        precision=1,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]] = hass.data[DOMAIN][
        config_entry.entry_id
    ][DATA_COORDINATOR]
    user_id = config_entry.data[CONF_ID]

    async_add_entities(
        HuisbaasjeSensor(coordinator, user_id, description)
        for description in SENSORS_INFO
    )


class HuisbaasjeSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, dict[str, Any]]]], SensorEntity
):
    """Defines a Huisbaasje sensor."""

    entity_description: HuisbaasjeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        user_id: str,
        description: HuisbaasjeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._source_type = description.key
        self._sensor_type = description.sensor_type
        self._precision = description.precision
        self._attr_unique_id = (
            f"{DOMAIN}_{user_id}_{description.key}_{description.sensor_type}"
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if (
            data := self.coordinator.data[self.entity_description.key][
                self.entity_description.sensor_type
            ]
        ) is not None:
            return round(data, self._precision)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(
            super().available
            and self.coordinator.data
            and self._source_type in self.coordinator.data
            and self.coordinator.data[self._source_type]
        )
