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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Connector
from .const import DOMAIN
from .entity import BlueCurrentEntity

TIMESTAMP_KEYS = ("start_datetime", "stop_datetime", "offline_since")

SENSORS = (
    SensorEntityDescription(
        key="actual_v1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        name="Voltage Phase 1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_v2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        name="Voltage Phase 2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_v3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        name="Voltage Phase 3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="avg_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        name="Average Voltage",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_p1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Current Phase 1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_p2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Current Phase 2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_p3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Current Phase 3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="avg_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Average Current",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="total_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        name="Total kW",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="actual_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        name="Energy Usage",
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="start_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Started On",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="stop_datetime",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Stopped On",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="offline_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Offline Since",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="total_cost",
        native_unit_of_measurement="EUR",
        device_class=SensorDeviceClass.MONETARY,
        name="Total Cost",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="vehicle_status",
        name="Vehicle Status",
        icon="mdi:car",
        device_class=SensorDeviceClass.ENUM,
        has_entity_name=True,
        options=["standby", "vehicle_detected", "ready", "no_power", "vehicle_error"],
        translation_key="vehicle_status",
    ),
    SensorEntityDescription(
        key="activity",
        name="Activity",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.ENUM,
        has_entity_name=True,
        options=["available", "charging", "unavailable", "error", "offline"],
        translation_key="activity",
    ),
    SensorEntityDescription(
        key="max_usage",
        name="Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="smartcharging_max_usage",
        name="Smart Charging Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="max_offline",
        name="Offline Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="current_left",
        name="Remaining current",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
)

GRID_SENSORS = (
    SensorEntityDescription(
        key="grid_actual_p1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Grid Current Phase 1",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="grid_actual_p2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Grid Current Phase 2",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="grid_actual_p3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Grid Current Phase 3",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="grid_avg_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Average Grid Current",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="grid_max_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        name="Max Grid Current",
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Blue Current sensors."""
    connector: Connector = hass.data[DOMAIN][entry.entry_id]
    sensor_list: list[SensorEntity] = []
    for evse_id in connector.charge_points:
        for sensor in SENSORS:
            sensor_list.append(ChargePointSensor(connector, sensor, evse_id))

    for grid_sensor in GRID_SENSORS:
        sensor_list.append(GridSensor(connector, grid_sensor))

    async_add_entities(sensor_list)


class ChargePointSensor(BlueCurrentEntity, SensorEntity):
    """Define a charge point sensor."""

    _attr_should_poll = False

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
            self._attr_available = True
            self._attr_native_value = new_value

        elif self.key not in TIMESTAMP_KEYS:
            self._attr_available = False


class GridSensor(SensorEntity):
    """Define a grid sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        connector: Connector,
        sensor: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        self.key = sensor.key
        self.entity_description = sensor
        self._attr_unique_id = sensor.key
        self.connector = connector

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{DOMAIN}_grid_update", update)
        )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the grid sensor from the latest data."""

        new_value = self.connector.grid.get(self.key)

        if new_value is not None:
            self._attr_available = True
            self._attr_native_value = new_value

        else:
            self._attr_available = False
