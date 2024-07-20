"""Platform for solarlog sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolarlogConfigEntry, SolarlogData
from .const import DOMAIN


@dataclass(frozen=True)
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="last_updated",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        translation_key="power_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        translation_key="power_dc",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        translation_key="voltage_ac",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        translation_key="voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        translation_key="yield_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        translation_key="yield_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        translation_key="yield_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        translation_key="yield_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        translation_key="yield_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        translation_key="consumption_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        translation_key="consumption_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        translation_key="consumption_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        translation_key="consumption_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        translation_key="consumption_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="self_consumption_year",
        translation_key="self_consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        translation_key="alternator_loss",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        translation_key="power_available",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        translation_key="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarlogConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add solarlog entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SolarlogSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SolarlogSensor(CoordinatorEntity[SolarlogData], SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    entity_description: SolarLogSensorEntityDescription

    def __init__(
        self,
        coordinator: SolarlogData,
        description: SolarLogSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer="Solar-Log",
            name=coordinator.name,
            configuration_url=coordinator.host,
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = self.coordinator.data.get(self.entity_description.key)

        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
