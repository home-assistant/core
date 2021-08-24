"""Support for Renault sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleChargeModeData,
    KamereonVehicleCockpitData,
    KamereonVehicleHvacStatusData,
)

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DEVICE_CLASS_CHARGE_MODE,
    DEVICE_CLASS_CHARGE_STATE,
    DEVICE_CLASS_PLUG_STATE,
    DOMAIN,
)
from .renault_entities import RenaultDataEntity, RenaultEntityDescription, T
from .renault_hub import RenaultHub


@dataclass
class RenaultSensorRequiredKeysMixin:
    """Mixin for required keys."""

    entity_class: type[RenaultSensor]


@dataclass
class RenaultSensorEntityDescription(
    SensorEntityDescription, RenaultEntityDescription, RenaultSensorRequiredKeysMixin
):
    """Class describing Renault sensor entities."""

    rounding: bool | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultSensor] = [
        description.entity_class(vehicle, description)
        for vehicle in proxy.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
        and (not description.requires_fuel or vehicle.details.uses_fuel())
    ]
    async_add_entities(entities)


class RenaultSensor(RenaultDataEntity[T], SensorEntity):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of this entity."""
        raw_value = self.data
        if raw_value is None:
            return None
        if self.entity_description.rounding:
            return round(cast(float, raw_value))
        return raw_value


class RenaultBatterySensor(RenaultSensor[KamereonVehicleBatteryStatusData]):
    """Renault battery sensor."""


class RenaultChargeModeSensor(RenaultSensor[KamereonVehicleChargeModeData]):
    """Renault charge mode sensor."""

    @property
    def icon(self) -> str:
        """Icon handling."""
        if self.data == "schedule_mode":
            return "mdi:calendar-clock"
        return "mdi:calendar-remove"


class RenaultCockpitSensor(RenaultSensor[KamereonVehicleCockpitData]):
    """Renault cockpit sensor."""


class RenaultHvacStatusSensor(RenaultSensor[KamereonVehicleHvacStatusData]):
    """Renault hvac status sensor."""


class RenaultBatteryChargeStateSensor(RenaultBatterySensor):
    """Charge State sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of this entity."""
        charging_status = (
            self.coordinator.data.get_charging_status()
            if self.coordinator.data
            else None
        )
        return charging_status.name.lower() if charging_status else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        if self.data == ChargeState.CHARGE_IN_PROGRESS.value:
            return "mdi:flash"
        return "mdi:flash-off"


class RenaultBatteryChargingPowerSensor(RenaultBatterySensor):
    """Charging Power sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the state of this entity."""
        raw_value = self.data
        if raw_value is None:
            return None
        if self.vehicle.details.reports_charging_power_in_watts():
            # Need to convert to kilowatts
            return cast(float, raw_value) / 1000
        return cast(float, raw_value)


class RenaultBatteryPlugStateSensor(RenaultBatterySensor):
    """Plug State sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of this entity."""
        plug_status = (
            self.coordinator.data.get_plug_status() if self.coordinator.data else None
        )
        return plug_status.name.lower() if plug_status else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        if self.data == PlugState.PLUGGED.value:
            return "mdi:power-plug"
        return "mdi:power-plug-off"


SENSOR_TYPES: tuple[RenaultSensorEntityDescription, ...] = (
    RenaultSensorEntityDescription(
        key="battery_level",
        coordinator="battery",
        data_key="batteryLevel",
        device_class=DEVICE_CLASS_BATTERY,
        entity_class=RenaultBatterySensor,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charge_state",
        coordinator="battery",
        data_key="chargingStatus",
        device_class=DEVICE_CLASS_CHARGE_STATE,
        entity_class=RenaultBatteryChargeStateSensor,
        name="Charge State",
    ),
    RenaultSensorEntityDescription(
        key="charging_remaining_time",
        coordinator="battery",
        data_key="chargingRemainingTime",
        entity_class=RenaultBatterySensor,
        icon="mdi:timer",
        name="Charging Remaining Time",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charging_power",
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=DEVICE_CLASS_POWER,
        entity_class=RenaultBatteryChargingPowerSensor,
        name="Charging Power",
        native_unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="plug_state",
        coordinator="battery",
        data_key="plugStatus",
        device_class=DEVICE_CLASS_PLUG_STATE,
        entity_class=RenaultBatteryPlugStateSensor,
        name="Plug State",
    ),
    RenaultSensorEntityDescription(
        key="battery_autonomy",
        coordinator="battery",
        data_key="batteryAutonomy",
        entity_class=RenaultBatterySensor,
        icon="mdi:ev-station",
        name="Battery Autonomy",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="battery_available_energy",
        coordinator="battery",
        data_key="batteryAvailableEnergy",
        entity_class=RenaultBatterySensor,
        device_class=DEVICE_CLASS_ENERGY,
        name="Battery Available Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="battery_temperature",
        coordinator="battery",
        data_key="batteryTemperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_class=RenaultBatterySensor,
        name="Battery Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="mileage",
        coordinator="cockpit",
        data_key="totalMileage",
        entity_class=RenaultCockpitSensor,
        icon="mdi:sign-direction",
        name="Mileage",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        rounding=True,
    ),
    RenaultSensorEntityDescription(
        key="fuel_autonomy",
        coordinator="cockpit",
        data_key="fuelAutonomy",
        entity_class=RenaultCockpitSensor,
        icon="mdi:gas-station",
        name="Fuel Autonomy",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
        requires_fuel=True,
        rounding=True,
    ),
    RenaultSensorEntityDescription(
        key="fuel_quantity",
        coordinator="cockpit",
        data_key="fuelQuantity",
        entity_class=RenaultCockpitSensor,
        icon="mdi:fuel",
        name="Fuel Quantity",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=STATE_CLASS_MEASUREMENT,
        requires_fuel=True,
        rounding=True,
    ),
    RenaultSensorEntityDescription(
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=DEVICE_CLASS_TEMPERATURE,
        data_key="externalTemperature",
        entity_class=RenaultHvacStatusSensor,
        name="Outside Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charge_mode",
        coordinator="charge_mode",
        data_key="chargeMode",
        device_class=DEVICE_CLASS_CHARGE_MODE,
        entity_class=RenaultChargeModeSensor,
        name="Charge Mode",
    ),
)
