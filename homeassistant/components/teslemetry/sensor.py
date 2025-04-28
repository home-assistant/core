"""Sensor platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from teslemetry_stream import TeslemetryStreamVehicle

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from homeassistant.util.variance import ignore_variance

from . import TeslemetryConfigEntry
from .const import ENERGY_HISTORY_FIELDS
from .entity import (
    TeslemetryEnergyHistoryEntity,
    TeslemetryEnergyInfoEntity,
    TeslemetryEnergyLiveEntity,
    TeslemetryVehicleEntity,
    TeslemetryVehicleStreamEntity,
    TeslemetryWallConnectorEntity,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0


CHARGE_STATES = {
    "Starting": "starting",
    "Charging": "charging",
    "Stopped": "stopped",
    "Complete": "complete",
    "Disconnected": "disconnected",
    "NoPower": "no_power",
}

SHIFT_STATES = {"P": "p", "D": "d", "R": "r", "N": "n"}

SENTRY_MODE_STATES = {
    "Off": "off",
    "Idle": "idle",
    "Armed": "armed",
    "Aware": "aware",
    "Panic": "panic",
    "Quiet": "quiet",
}


@dataclass(frozen=True, kw_only=True)
class TeslemetryVehicleSensorEntityDescription(SensorEntityDescription):
    """Describes Teslemetry Sensor entity."""

    polling: bool = False
    polling_value_fn: Callable[[StateType], StateType] = lambda x: x
    nullable: bool = False
    streaming_listener: (
        Callable[
            [TeslemetryStreamVehicle, Callable[[StateType], None]],
            Callable[[], None],
        ]
        | None
    ) = None
    streaming_firmware: str = "2024.26"


VEHICLE_DESCRIPTIONS: tuple[TeslemetryVehicleSensorEntityDescription, ...] = (
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charging_state",
        polling=True,
        streaming_listener=lambda x, y: x.listen_DetailedChargeState(
            lambda z: None if z is None else y(z.lower())
        ),
        polling_value_fn=lambda value: CHARGE_STATES.get(str(value)),
        options=list(CHARGE_STATES.values()),
        device_class=SensorDeviceClass.ENUM,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_battery_level",
        polling=True,
        streaming_listener=lambda x, y: x.listen_BatteryLevel(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_usable_battery_level",
        polling=True,
        streaming_listener=lambda x, y: x.listen_Soc(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charge_energy_added",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ACChargingEnergyIn(y),
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charger_power",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ACChargingPower(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charger_voltage",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ChargerVoltage(y),
        streaming_firmware="2024.44.32",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charger_actual_current",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ChargeAmps(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_charge_rate",
        polling=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_conn_charge_cable",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ChargingCableType(y),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_fast_charger_type",
        polling=True,
        streaming_listener=lambda x, y: x.listen_FastChargerType(y),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_battery_range",
        polling=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_est_battery_range",
        polling=True,
        streaming_listener=lambda x, y: x.listen_EstBatteryRange(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="charge_state_ideal_battery_range",
        polling=True,
        streaming_listener=lambda x, y: x.listen_IdealBatteryRange(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_speed",
        polling=True,
        polling_value_fn=lambda value: value or 0,
        streaming_listener=lambda x, y: x.listen_VehicleSpeed(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_power",
        polling=True,
        polling_value_fn=lambda value: value or 0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_shift_state",
        polling=True,
        polling_value_fn=lambda x: SHIFT_STATES.get(str(x), "p"),
        nullable=True,
        streaming_listener=lambda x, y: x.listen_Gear(
            lambda z: y("p" if z is None else z.lower())
        ),
        options=list(SHIFT_STATES.values()),
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="vehicle_state_odometer",
        polling=True,
        streaming_listener=lambda x, y: x.listen_Odometer(y),
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="vehicle_state_tpms_pressure_fl",
        polling=True,
        streaming_listener=lambda x, y: x.listen_TpmsPressureFl(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="vehicle_state_tpms_pressure_fr",
        polling=True,
        streaming_listener=lambda x, y: x.listen_TpmsPressureFr(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="vehicle_state_tpms_pressure_rl",
        polling=True,
        streaming_listener=lambda x, y: x.listen_TpmsPressureRl(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="vehicle_state_tpms_pressure_rr",
        polling=True,
        streaming_listener=lambda x, y: x.listen_TpmsPressureRr(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="climate_state_inside_temp",
        polling=True,
        streaming_listener=lambda x, y: x.listen_InsideTemp(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="climate_state_outside_temp",
        polling=True,
        streaming_listener=lambda x, y: x.listen_OutsideTemp(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="climate_state_driver_temp_setting",
        polling=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="climate_state_passenger_temp_setting",
        polling=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_active_route_traffic_minutes_delay",
        polling=True,
        streaming_listener=lambda x, y: x.listen_RouteTrafficMinutesDelay(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_active_route_energy_at_arrival",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ExpectedEnergyPercentAtTripArrival(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="drive_state_active_route_miles_to_arrival",
        polling=True,
        streaming_listener=lambda x, y: x.listen_MilesToArrival(y),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    TeslemetryVehicleSensorEntityDescription(
        key="sentry_mode",
        streaming_listener=lambda x, y: x.listen_SentryMode(y),
        options=list(SENTRY_MODE_STATES.values()),
        device_class=SensorDeviceClass.ENUM,
    ),
)


@dataclass(frozen=True, kw_only=True)
class TeslemetryTimeEntityDescription(SensorEntityDescription):
    """Describes Teslemetry Sensor entity."""

    variance: int
    streaming_listener: Callable[
        [TeslemetryStreamVehicle, Callable[[float | None], None]],
        Callable[[], None],
    ]
    streaming_firmware: str = "2024.26"
    streaming_unit: str


VEHICLE_TIME_DESCRIPTIONS: tuple[TeslemetryTimeEntityDescription, ...] = (
    TeslemetryTimeEntityDescription(
        key="charge_state_minutes_to_full_charge",
        streaming_listener=lambda x, y: x.listen_TimeToFullCharge(y),
        streaming_unit="hours",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        variance=4,
    ),
    TeslemetryTimeEntityDescription(
        key="drive_state_active_route_minutes_to_arrival",
        streaming_listener=lambda x, y: x.listen_MinutesToArrival(y),
        streaming_unit="minutes",
        device_class=SensorDeviceClass.TIMESTAMP,
        variance=1,
    ),
)


@dataclass(frozen=True, kw_only=True)
class TeslemetryEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Teslemetry Sensor entity."""

    value_fn: Callable[[StateType], StateType | datetime] = lambda x: x


ENERGY_LIVE_DESCRIPTIONS: tuple[TeslemetryEnergySensorEntityDescription, ...] = (
    TeslemetryEnergySensorEntityDescription(
        key="solar_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="energy_left",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="total_pack_energy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="percentage_charged",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=2,
        value_fn=lambda value: value or 0,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="battery_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="load_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="grid_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="grid_services_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="generator_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    TeslemetryEnergySensorEntityDescription(
        key="island_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "on_grid",
            "off_grid",
            "off_grid_intentional",
            "off_grid_unintentional",
            "island_status_unknown",
        ],
    ),
)


@dataclass(frozen=True, kw_only=True)
class TeslemetrySensorEntityDescription(SensorEntityDescription):
    """Describes Teslemetry Sensor entity."""

    value_fn: Callable[[StateType], StateType] = lambda x: x


WALL_CONNECTOR_DESCRIPTIONS: tuple[TeslemetrySensorEntityDescription, ...] = (
    TeslemetrySensorEntityDescription(
        key="wall_connector_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="wall_connector_fault_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetrySensorEntityDescription(
        key="wall_connector_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
    ),
    TeslemetrySensorEntityDescription(
        key="vin",
        value_fn=lambda vin: vin or "disconnected",
    ),
)

ENERGY_INFO_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="vpp_backup_reserve_percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(key="version"),
)

ENERGY_HISTORY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = tuple(
    SensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=(
            key.startswith("total") or key == "grid_energy_imported"
        ),
    )
    for key in ENERGY_HISTORY_FIELDS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry sensor platform from a config entry."""

    entities: list[SensorEntity] = []
    for vehicle in entry.runtime_data.vehicles:
        for description in VEHICLE_DESCRIPTIONS:
            if (
                not vehicle.api.pre2021
                and description.streaming_listener
                and vehicle.firmware >= description.streaming_firmware
            ):
                entities.append(TeslemetryStreamSensorEntity(vehicle, description))
            elif description.polling:
                entities.append(TeslemetryVehicleSensorEntity(vehicle, description))

        for time_description in VEHICLE_TIME_DESCRIPTIONS:
            if (
                not vehicle.api.pre2021
                and vehicle.firmware >= time_description.streaming_firmware
            ):
                entities.append(
                    TeslemetryStreamTimeSensorEntity(vehicle, time_description)
                )
            else:
                entities.append(
                    TeslemetryVehicleTimeSensorEntity(vehicle, time_description)
                )

    entities.extend(
        TeslemetryEnergyLiveSensorEntity(energysite, description)
        for energysite in entry.runtime_data.energysites
        if energysite.live_coordinator
        for description in ENERGY_LIVE_DESCRIPTIONS
        if description.key in energysite.live_coordinator.data
        or description.key == "percentage_charged"
    )

    entities.extend(
        TeslemetryWallConnectorSensorEntity(energysite, din, description)
        for energysite in entry.runtime_data.energysites
        if energysite.live_coordinator
        for din in energysite.live_coordinator.data.get("wall_connectors", {})
        for description in WALL_CONNECTOR_DESCRIPTIONS
    )

    entities.extend(
        TeslemetryEnergyInfoSensorEntity(energysite, description)
        for energysite in entry.runtime_data.energysites
        for description in ENERGY_INFO_DESCRIPTIONS
        if description.key in energysite.info_coordinator.data
    )

    entities.extend(
        TeslemetryEnergyHistorySensorEntity(energysite, description)
        for energysite in entry.runtime_data.energysites
        for description in ENERGY_HISTORY_DESCRIPTIONS
        if energysite.history_coordinator is not None
    )

    async_add_entities(entities)


class TeslemetryStreamSensorEntity(TeslemetryVehicleStreamEntity, RestoreSensor):
    """Base class for Teslemetry vehicle streaming sensors."""

    entity_description: TeslemetryVehicleSensorEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryVehicleSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value

        if self.entity_description.streaming_listener is not None:
            self.async_on_remove(
                self.entity_description.streaming_listener(
                    self.vehicle.stream_vehicle, self._async_value_from_stream
                )
            )

    def _async_value_from_stream(self, value: StateType) -> None:
        """Update the value of the entity."""
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryVehicleSensorEntity(TeslemetryVehicleEntity, SensorEntity):
    """Base class for Teslemetry vehicle metric sensors."""

    entity_description: TeslemetryVehicleSensorEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryVehicleSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self.entity_description.nullable or self._value is not None:
            self._attr_available = True
            self._attr_native_value = self.entity_description.polling_value_fn(
                self._value
            )
        else:
            self._attr_available = False
            self._attr_native_value = None


class TeslemetryStreamTimeSensorEntity(TeslemetryVehicleStreamEntity, SensorEntity):
    """Base class for Teslemetry vehicle streaming sensors."""

    entity_description: TeslemetryTimeEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryTimeEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._get_timestamp = ignore_variance(
            func=lambda value: dt_util.now()
            + timedelta(**{self.entity_description.streaming_unit: value}),
            ignored_variance=timedelta(minutes=description.variance),
        )
        super().__init__(data, description.key)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.entity_description.streaming_listener(
                self.vehicle.stream_vehicle, self._value_callback
            )
        )

    def _value_callback(self, value: float | None) -> None:
        """Update the value of the entity."""
        if value is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = self._get_timestamp(value)
        self.async_write_ha_state()


class TeslemetryVehicleTimeSensorEntity(TeslemetryVehicleEntity, SensorEntity):
    """Base class for Teslemetry vehicle time sensors."""

    entity_description: TeslemetryTimeEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryTimeEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._get_timestamp = ignore_variance(
            func=lambda value: dt_util.now() + timedelta(minutes=value),
            ignored_variance=timedelta(minutes=description.variance),
        )

        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = isinstance(self._value, int | float) and self._value > 0
        if self._attr_available:
            self._attr_native_value = self._get_timestamp(self._value)


class TeslemetryEnergyLiveSensorEntity(TeslemetryEnergyLiveEntity, SensorEntity):
    """Base class for Teslemetry energy site metric sensors."""

    entity_description: TeslemetryEnergySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetryEnergySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = not self.is_none
        self._attr_native_value = self.entity_description.value_fn(self._value)


class TeslemetryWallConnectorSensorEntity(TeslemetryWallConnectorEntity, SensorEntity):
    """Base class for Teslemetry energy site metric sensors."""

    entity_description: TeslemetrySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        din: str,
        description: TeslemetrySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(
            data,
            din,
            description.key,
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self.exists:
            self._attr_native_value = self.entity_description.value_fn(self._value)


class TeslemetryEnergyInfoSensorEntity(TeslemetryEnergyInfoEntity, SensorEntity):
    """Base class for Teslemetry energy site metric sensors."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = not self.is_none
        self._attr_native_value = self._value


class TeslemetryEnergyHistorySensorEntity(TeslemetryEnergyHistoryEntity, SensorEntity):
    """Base class for Tesla Fleet energy site metric sensors."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self._value
