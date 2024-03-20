"""Support for Blue Current sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Connector
from .const import DOMAIN
from .entity import BlueCurrentEntity, ChargepointEntity

TIMESTAMP_KEYS = ("start_datetime", "stop_datetime", "offline_since")

SENSORS = (
    SensorEntityDescription(
        key="actual_v1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        translation_key="actual_v1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_v2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        translation_key="actual_v2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_v3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        translation_key="actual_v3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="avg_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        translation_key="avg_voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_p1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="actual_p1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_p2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="actual_p2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_p3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="actual_p3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="avg_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="avg_current",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        translation_key="total_kw",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        translation_key="actual_kwh",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="start_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="start_datetime",
    ),
    SensorEntityDescription(
        key="stop_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="stop_datetime",
    ),
    SensorEntityDescription(
        key="offline_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="offline_since",
    ),
    SensorEntityDescription(
        key="total_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        translation_key="total_cost",
    ),
    SensorEntityDescription(
        key="vehicle_status",
        device_class=SensorDeviceClass.ENUM,
        options=["standby", "vehicle_detected", "ready", "no_power", "vehicle_error"],
        translation_key="vehicle_status",
    ),
    SensorEntityDescription(
        key="activity",
        device_class=SensorDeviceClass.ENUM,
        options=["available", "charging", "unavailable", "error", "offline"],
        translation_key="activity",
    ),
    SensorEntityDescription(
        key="max_usage",
        translation_key="max_usage",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="smartcharging_max_usage",
        translation_key="smartcharging_max_usage",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="max_offline",
        translation_key="max_offline",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_left",
        translation_key="current_left",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

GRID_SENSORS = (
    SensorEntityDescription(
        key="grid_actual_p1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="grid_actual_p1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_actual_p2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="grid_actual_p2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_actual_p3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="grid_actual_p3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_avg_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="grid_avg_current",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="grid_max_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        translation_key="grid_max_current",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Blue Current sensors."""
    connector: Connector = hass.data[DOMAIN][entry.entry_id]
    sensor_list: list[SensorEntity] = [
        ChargePointSensor(connector, sensor, evse_id)
        for evse_id in connector.charge_points
        for sensor in SENSORS
    ]

    sensor_list.extend(GridSensor(connector, sensor) for sensor in GRID_SENSORS)

    async_add_entities(sensor_list)


class ChargePointSensor(ChargepointEntity, SensorEntity):
    """Define a charge point sensor."""

    def __init__(
        self,
        connector: Connector,
        sensor: SensorEntityDescription,
        evse_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(connector, evse_id)

        self.key = sensor.key
        self.entity_description = sensor
        self._attr_unique_id = f"{sensor.key}_{evse_id}"

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor from the latest data."""

        new_value = self.connector.charge_points[self.evse_id].get(self.key)

        if new_value is not None:
            if self.key in TIMESTAMP_KEYS and not (
                self._attr_native_value is None or self._attr_native_value < new_value
            ):
                return
            self.has_value = True
            self._attr_native_value = new_value

        elif self.key not in TIMESTAMP_KEYS:
            self.has_value = False


class GridSensor(BlueCurrentEntity, SensorEntity):
    """Define a grid sensor."""

    def __init__(
        self,
        connector: Connector,
        sensor: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(connector, f"{DOMAIN}_grid_update")

        self.key = sensor.key
        self.entity_description = sensor
        self._attr_unique_id = sensor.key

    @callback
    def update_from_latest_data(self) -> None:
        """Update the grid sensor from the latest data."""

        new_value = self.connector.grid.get(self.key)

        if new_value is not None:
            self.has_value = True
            self._attr_native_value = new_value

        else:
            self.has_value = False
