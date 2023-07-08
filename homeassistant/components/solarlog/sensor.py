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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_local

from . import SolarlogData
from .const import DOMAIN


@dataclass
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="time",
        name="last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=as_local,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        name="voltage AC",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        name="voltage DC",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        name="yield yesterday",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        name="yield month",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        name="yield year",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        name="consumption AC",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        name="consumption day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        name="consumption yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        name="consumption month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        name="consumption year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        name="consumption total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        name="capacity",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        name="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        name="power available",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        name="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add solarlog entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolarlogSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SolarlogSensor(CoordinatorEntity[SolarlogData], SensorEntity):
    """Representation of a Sensor."""

    entity_description: SolarLogSensorEntityDescription

    def __init__(
        self,
        coordinator: SolarlogData,
        description: SolarLogSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
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
        raw_attr = getattr(self.coordinator.data, self.entity_description.key)
        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
