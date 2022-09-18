"""Support for Renault sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, cast

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleCockpitData,
    KamereonVehicleHvacStatusData,
    KamereonVehicleLocationData,
    KamereonVehicleResStateData,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
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
from homeassistant.util.dt import as_utc, parse_datetime

from .const import DEVICE_CLASS_CHARGE_STATE, DEVICE_CLASS_PLUG_STATE, DOMAIN
from .renault_coordinator import T
from .renault_entities import RenaultDataEntity, RenaultDataEntityDescription
from .renault_hub import RenaultHub
from .renault_vehicle import RenaultVehicleProxy


@dataclass
class RenaultSensorRequiredKeysMixin(Generic[T]):
    """Mixin for required keys."""

    data_key: str
    entity_class: type[RenaultSensor[T]]


@dataclass
class RenaultSensorEntityDescription(
    SensorEntityDescription,
    RenaultDataEntityDescription,
    RenaultSensorRequiredKeysMixin[T],
):
    """Class describing Renault sensor entities."""

    icon_lambda: Callable[[RenaultSensor[T]], str] | None = None
    condition_lambda: Callable[[RenaultVehicleProxy], bool] | None = None
    requires_fuel: bool = False
    value_lambda: Callable[[RenaultSensor[T]], StateType | datetime] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultSensor[Any]] = [
        description.entity_class(vehicle, description)
        for vehicle in proxy.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
        and (not description.requires_fuel or vehicle.details.uses_fuel())
        and (not description.condition_lambda or description.condition_lambda(vehicle))
    ]
    async_add_entities(entities)


class RenaultSensor(RenaultDataEntity[T], SensorEntity):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSensorEntityDescription[T]

    @property
    def data(self) -> StateType:
        """Return the state of this entity."""
        return self._get_data_attr(self.entity_description.data_key)

    @property
    def icon(self) -> str | None:
        """Icon handling."""
        if self.entity_description.icon_lambda is None:
            return super().icon
        return self.entity_description.icon_lambda(self)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of this entity."""
        if self.data is None:
            return None
        if self.entity_description.value_lambda is None:
            return self.data
        return self.entity_description.value_lambda(self)


def _get_charging_power(entity: RenaultSensor[T]) -> StateType:
    """Return the charging_power of this entity."""
    return cast(float, entity.data) / 1000


def _get_charge_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the charging_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    charging_status = data.get_charging_status() if data else None
    return charging_status.name.lower() if charging_status else None


def _get_charge_state_icon(entity: RenaultSensor[T]) -> str:
    """Return the icon of this entity."""
    if entity.data == ChargeState.CHARGE_IN_PROGRESS.value:
        return "mdi:flash"
    return "mdi:flash-off"


def _get_plug_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the plug_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    plug_status = data.get_plug_status() if data else None
    return plug_status.name.lower() if plug_status else None


def _get_plug_state_icon(entity: RenaultSensor[T]) -> str:
    """Return the icon of this entity."""
    if entity.data == PlugState.PLUGGED.value:
        return "mdi:power-plug"
    return "mdi:power-plug-off"


def _get_rounded_value(entity: RenaultSensor[T]) -> float:
    """Return the icon of this entity."""
    return round(cast(float, entity.data))


def _get_utc_value(entity: RenaultSensor[T]) -> datetime:
    """Return the UTC value of this entity."""
    original_dt = parse_datetime(cast(str, entity.data))
    if TYPE_CHECKING:
        assert original_dt is not None
    return as_utc(original_dt)


SENSOR_TYPES: tuple[RenaultSensorEntityDescription[Any], ...] = (
    RenaultSensorEntityDescription(
        key="battery_level",
        coordinator="battery",
        data_key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charge_state",
        coordinator="battery",
        data_key="chargingStatus",
        device_class=DEVICE_CLASS_CHARGE_STATE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        icon_lambda=_get_charge_state_icon,
        name="Charge state",
        value_lambda=_get_charge_state_formatted,
    ),
    RenaultSensorEntityDescription(
        key="charging_remaining_time",
        coordinator="battery",
        data_key="chargingRemainingTime",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        icon="mdi:timer",
        name="Charging remaining time",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charging_power",
        condition_lambda=lambda a: not a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.CURRENT,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        name="Charging power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charging_power",
        condition_lambda=lambda a: a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        name="Charging power",
        native_unit_of_measurement=POWER_KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=_get_charging_power,
    ),
    RenaultSensorEntityDescription(
        key="plug_state",
        coordinator="battery",
        data_key="plugStatus",
        device_class=DEVICE_CLASS_PLUG_STATE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        icon_lambda=_get_plug_state_icon,
        name="Plug state",
        value_lambda=_get_plug_state_formatted,
    ),
    RenaultSensorEntityDescription(
        key="battery_autonomy",
        coordinator="battery",
        data_key="batteryAutonomy",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        icon="mdi:ev-station",
        name="Battery autonomy",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="battery_available_energy",
        coordinator="battery",
        data_key="batteryAvailableEnergy",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        device_class=SensorDeviceClass.ENERGY,
        name="Battery available energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="battery_temperature",
        coordinator="battery",
        data_key="batteryTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        name="Battery temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="battery_last_activity",
        coordinator="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="timestamp",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        entity_registry_enabled_default=False,
        name="Battery last activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="mileage",
        coordinator="cockpit",
        data_key="totalMileage",
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        icon="mdi:sign-direction",
        name="Mileage",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_lambda=_get_rounded_value,
    ),
    RenaultSensorEntityDescription(
        key="fuel_autonomy",
        coordinator="cockpit",
        data_key="fuelAutonomy",
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        icon="mdi:gas-station",
        name="Fuel autonomy",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
    ),
    RenaultSensorEntityDescription(
        key="fuel_quantity",
        coordinator="cockpit",
        data_key="fuelQuantity",
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        icon="mdi:fuel",
        name="Fuel quantity",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
    ),
    RenaultSensorEntityDescription(
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TEMPERATURE,
        data_key="externalTemperature",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        name="Outside temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="hvac_soc_threshold",
        coordinator="hvac_status",
        data_key="socThreshold",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        name="HVAC SoC threshold",
        native_unit_of_measurement=PERCENTAGE,
    ),
    RenaultSensorEntityDescription(
        key="hvac_last_activity",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        entity_registry_enabled_default=False,
        name="HVAC last activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="location_last_activity",
        coordinator="location",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleLocationData],
        entity_registry_enabled_default=False,
        name="Location last activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="res_state",
        coordinator="res_state",
        data_key="details",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        name="Remote engine start",
    ),
    RenaultSensorEntityDescription(
        key="res_state_code",
        coordinator="res_state",
        data_key="code",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        entity_registry_enabled_default=False,
        name="Remote engine start code",
    ),
)
