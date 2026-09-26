"""Support for Škoda sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import override

from skoda_public_api.models.enums import (
    AirConditioningState,
    AuxiliaryHeatingStartMode,
    AuxiliaryHeatingState,
    ChargeType,
    ChargingState,
    TemperatureUnit,
    VehicleCapability,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import SkodaUpdateCoordinator
from .entity import SkodaEntity
from .models import SkodaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_COMBUSTION_CAR_TYPES = frozenset(
    {
        VehicleCapability.VEHICLE_TYPE_GASOLINE,
        VehicleCapability.VEHICLE_TYPE_DIESEL,
        VehicleCapability.VEHICLE_TYPE_HYBRID,
        VehicleCapability.VEHICLE_TYPE_CNG,
        VehicleCapability.VEHICLE_TYPE_LPG,
    }
)

_CHARGING_STATE_MAP = {
    ChargingState.CHARGING: "charging",
    ChargingState.CONNECT_CABLE: "connect_cable",
    ChargingState.READY_FOR_CHARGING: "ready_for_charging",
    ChargingState.CONSERVING: "conserving",
    ChargingState.DISCHARGING: "discharging",
    ChargingState.CHARGING_INTERRUPTED: "charging_interrupted",
}

_CHARGE_TYPE_MAP = {
    ChargeType.AC: "ac",
    ChargeType.DC: "dc",
    ChargeType.OFF: "off",
}

_AUXILIARY_HEATING_START_MODE_MAP = {
    AuxiliaryHeatingStartMode.HEATING: "heating",
    AuxiliaryHeatingStartMode.VENTILATION: "ventilation",
}


@dataclass(frozen=True, kw_only=True)
class SkodaSensorEntityDescription(SensorEntityDescription):
    """Describes a Škoda sensor entity."""

    value_fn: Callable[[SkodaEntity], StateType | datetime]
    unit_fn: Callable[[SkodaEntity], str] | None = None
    required_capabilities: frozenset[VehicleCapability] = frozenset()
    is_supported_fn: Callable[[set[VehicleCapability]], bool] | None = None

    def is_supported(self, capabilities: set[VehicleCapability]) -> bool:
        """Return whether the vehicle's capabilities satisfy this entity's requirements."""
        if not self.required_capabilities <= capabilities:
            return False
        if self.is_supported_fn is not None:
            return self.is_supported_fn(capabilities)
        return True


def _mileage_value(entity: SkodaEntity) -> int | None:
    odometer = entity.open_api_odometer
    if odometer and odometer.mileage_in_km is not None:
        return odometer.mileage_in_km
    return None


def _last_synchronization_value(entity: SkodaEntity) -> datetime | None:
    status = entity.open_api_vehicle_status
    if status is None or not status.car_captured_timestamp:
        return None

    timestamp = status.car_captured_timestamp
    if isinstance(timestamp, datetime):
        return dt_util.as_utc(timestamp)

    parsed_dt = dt_util.parse_datetime(str(timestamp))
    return dt_util.as_utc(parsed_dt) if parsed_dt else None


def _fuel_level_value(entity: SkodaEntity) -> int | None:
    driving_range = entity.open_api_driving_range
    if driving_range is not None:
        primary_engine = driving_range.primary_engine_range
        if (
            primary_engine is not None
            and primary_engine.current_fuel_level_in_percent is not None
        ):
            return primary_engine.current_fuel_level_in_percent

        secondary_engine = driving_range.secondary_engine_range
        if secondary_engine is not None:
            return secondary_engine.current_fuel_level_in_percent

    return None


def _fuel_level_supported(capabilities: set[VehicleCapability]) -> bool:
    """Require a combustion-capable car type in addition to FUEL_STATUS.

    An electric vehicle also reports FUEL_STATUS but never a fuel level,
    which would otherwise create a permanently unknown entity.
    """
    return bool(capabilities & _COMBUSTION_CAR_TYPES)


def _battery_percentage_value(entity: SkodaEntity) -> int | None:
    charging = entity.open_api_charging
    if (
        charging is not None
        and charging.status is not None
        and charging.status.battery is not None
    ):
        return charging.status.battery.state_of_charge_in_percent
    return None


def _total_range_value(entity: SkodaEntity) -> int | float | None:
    driving_range = entity.open_api_driving_range
    if driving_range is not None:
        return driving_range.total_range_in_km
    return None


def _electric_range_value(entity: SkodaEntity) -> int | float | None:
    charging = entity.open_api_charging
    if (
        charging is not None
        and charging.status is not None
        and charging.status.battery is not None
        and charging.status.battery.remaining_cruising_range_in_meters is not None
    ):
        return charging.status.battery.remaining_cruising_range_in_meters / 1000
    return None


def _remaining_ac_time_value(entity: SkodaEntity) -> datetime | None:
    ac = entity.open_api_air_conditioning
    if not ac or ac.state in [
        AirConditioningState.OFF,
        AirConditioningState.UNKNOWN,
        AirConditioningState.UNSUPPORTED,
    ]:
        return None

    target_timestamp = ac.estimated_reach_of_target_temperature_at
    if target_timestamp is None:
        return None

    if isinstance(target_timestamp, datetime):
        return dt_util.as_utc(target_timestamp)

    parsed_dt = dt_util.parse_datetime(str(target_timestamp))
    return dt_util.as_utc(parsed_dt) if parsed_dt else None


def _charging_power_value(entity: SkodaEntity) -> float | None:
    charging = entity.open_api_charging
    if not charging or not charging.status:
        return None
    if charging.status.state != ChargingState.CHARGING:
        return None
    return charging.status.charge_power_in_kw


def _charging_state_value(entity: SkodaEntity) -> str | None:
    charging = entity.open_api_charging
    if not charging or not charging.status:
        return None
    return _CHARGING_STATE_MAP.get(charging.status.state)


def _remaining_time_to_full_charge_value(entity: SkodaEntity) -> float | None:
    charging = entity.open_api_charging
    if not charging or not charging.status:
        return None
    if charging.status.state != ChargingState.CHARGING:
        return None
    return charging.status.remaining_time_to_fully_charged_in_minutes


def _charge_type_value(entity: SkodaEntity) -> str | None:
    charging = entity.open_api_charging
    if not charging or not charging.status or not charging.status.state:
        return None

    if charging.status.state != ChargingState.CHARGING:
        return "not_charging"

    if not charging.status.charge_type:
        return None

    return _CHARGE_TYPE_MAP.get(charging.status.charge_type)


def _auxiliary_heating_mode_value(entity: SkodaEntity) -> str | None:
    aux_heat = entity.open_api_auxiliary_heating
    if aux_heat is None or aux_heat.start_mode is None:
        return None
    return _AUXILIARY_HEATING_START_MODE_MAP.get(aux_heat.start_mode)


def _aux_heating_duration_value(entity: SkodaEntity) -> int | None:
    aux_heat = entity.open_api_auxiliary_heating
    if not aux_heat or aux_heat.state in [
        AuxiliaryHeatingState.OFF,
        AuxiliaryHeatingState.UNKNOWN,
        AuxiliaryHeatingState.UNSUPPORTED,
    ]:
        return None
    return aux_heat.duration_in_seconds


def _preset_temperature_value(entity: SkodaEntity) -> float | None:
    ac = entity.open_api_air_conditioning
    if not ac or ac.target_temperature is None:
        return None
    return ac.target_temperature.value


def _preset_temperature_unit(entity: SkodaEntity) -> str:
    ac = entity.open_api_air_conditioning
    if (
        ac
        and ac.target_temperature
        and ac.target_temperature.unit == TemperatureUnit.FAHRENHEIT
    ):
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def _licence_plate_value(entity: SkodaEntity) -> str | None:
    vehicle = entity.open_api_vehicle
    if vehicle and vehicle.license_plate:
        return vehicle.license_plate
    return None


SENSOR_TYPES: tuple[SkodaSensorEntityDescription, ...] = (
    SkodaSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:car-info",
        required_capabilities=frozenset({VehicleCapability.ODOMETER}),
        value_fn=_mileage_value,
    ),
    SkodaSensorEntityDescription(
        key="timestamp_last_sync",
        translation_key="timestamp_last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-sync-outline",
        value_fn=_last_synchronization_value,
    ),
    SkodaSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gas-station",
        required_capabilities=frozenset({VehicleCapability.FUEL_STATUS}),
        is_supported_fn=_fuel_level_supported,
        value_fn=_fuel_level_value,
    ),
    SkodaSensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_battery_percentage_value,
    ),
    SkodaSensorEntityDescription(
        key="remaining_range",
        translation_key="total_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control",
        required_capabilities=frozenset({VehicleCapability.FUEL_STATUS}),
        value_fn=_total_range_value,
    ),
    SkodaSensorEntityDescription(
        key="remaining_electric_range",
        translation_key="electric_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_electric_range_value,
    ),
    SkodaSensorEntityDescription(
        key="remaining_ac_time",
        translation_key="remaining_ac_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-digital",
        required_capabilities=frozenset({VehicleCapability.AIR_CONDITIONING}),
        value_fn=_remaining_ac_time_value,
    ),
    SkodaSensorEntityDescription(
        key="charging_power",
        translation_key="charging_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_charging_power_value,
    ),
    SkodaSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "charging",
            "connect_cable",
            "ready_for_charging",
            "conserving",
            "discharging",
            "charging_interrupted",
        ],
        icon="mdi:battery-charging",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_charging_state_value,
    ),
    SkodaSensorEntityDescription(
        key="remaining_time_to_full_battery",
        translation_key="remaining_time_to_full_battery",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:battery-charging-medium",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_remaining_time_to_full_charge_value,
    ),
    SkodaSensorEntityDescription(
        key="charge_type",
        translation_key="charge_type",
        device_class=SensorDeviceClass.ENUM,
        options=["ac", "dc", "off", "not_charging"],
        icon="mdi:connection",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_charge_type_value,
    ),
    SkodaSensorEntityDescription(
        key="auxiliary_heating_mode",
        translation_key="auxiliary_heating_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["heating", "ventilation"],
        icon="mdi:heating-coil",
        required_capabilities=frozenset({VehicleCapability.AUXILIARY_HEATING}),
        value_fn=_auxiliary_heating_mode_value,
    ),
    SkodaSensorEntityDescription(
        key="aux_heating_duration",
        translation_key="aux_heating_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:fan-clock",
        required_capabilities=frozenset({VehicleCapability.AUXILIARY_HEATING}),
        value_fn=_aux_heating_duration_value,
    ),
    SkodaSensorEntityDescription(
        key="preset_temperature_value",
        translation_key="preset_temperature_value",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
        required_capabilities=frozenset({VehicleCapability.AIR_CONDITIONING}),
        value_fn=_preset_temperature_value,
        unit_fn=_preset_temperature_unit,
    ),
    SkodaSensorEntityDescription(
        key="licence_plate",
        translation_key="licence_plate",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alpha-r-box-outline",
        value_fn=_licence_plate_value,
    ),
)


class SkodaSensor(SkodaEntity, SensorEntity):
    """Generic Škoda sensor entity, driven entirely by its entity description."""

    entity_description: SkodaSensorEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor with a coordinator and its entity description."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor, computed by the entity description."""
        return self.entity_description.value_fn(self)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement, computed dynamically if the description asks for it."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self)
        return super().native_unit_of_measurement


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda sensors from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    vehicle_response = coordinator.data.vehicle_response if coordinator.data else None
    capabilities = (
        vehicle_response.supported_capabilities() if vehicle_response else set()
    )
    vin = vehicle_response.vehicle.vin if vehicle_response else None
    _LOGGER.debug("[%s] CAPABILITIES: %s", vin, capabilities)

    async_add_entities(
        SkodaSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.is_supported(capabilities)
    )
