"""Support for Škoda sensors."""

from collections.abc import Callable, Sequence
from datetime import datetime
from enum import StrEnum
import logging
from typing import Any, override

from skoda_public_api.models.common import VehicleError
from skoda_public_api.models.enums import (
    AirConditioningState,
    ChargeType,
    ChargingState,
    TemperatureUnit,
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SkodaUpdateCoordinator
from .entity import SkodaEntity
from .models import SkodaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class Capability(StrEnum):
    """Capabilities a Škoda vehicle may support."""

    STATUS = "status"
    ODOMETER = "odometer"
    POSITION = "parking_position"
    CHARGING = "charging"
    CHARGING_PROFILES = "charging_profiles"
    AIR_CONDITIONING = "air_conditioning"
    VENTILATION = "active_ventilation"
    AUXILIARY_HEATING = "auxiliary_heating"
    FUEL_STATUS = "fuel_status"
    ADBLUE = "ad_blue_range"
    CT_ELECTRIC = "ct_electric"
    CT_HYBRID = "ct_hybrid"
    CT_GASOLINE = "ct_gasoline"
    CT_DIESEL = "ct_diesel"
    CT_CNG = "ct_cng"
    CT_LPG = "ct_lpg"
    SUNROOF = "sunroof"


# Capabilities whose top-level API field can report a transient
# "<FEATURE>_UNAVAILABLE" error (as opposed to a permanent "_UNSUPPORTED" or
# "_DISABLED" one) in VehicleResponse.errors. These must still be treated as
# supported when their field is empty for that reason, otherwise a temporary
# hiccup in the first response would hide the entity for the entry's lifetime
# (entities are only created once, at setup).
_TRANSIENT_ERROR_PREFIXES: dict[Capability, str] = {
    Capability.STATUS: "VEHICLE_STATUS",
    Capability.ODOMETER: "ODOMETER",
    Capability.POSITION: "PARKING_POSITION",
    Capability.CHARGING: "CHARGING",
    Capability.AIR_CONDITIONING: "AIR_CONDITIONING",
    Capability.VENTILATION: "ACTIVE_VENTILATION",
    Capability.AUXILIARY_HEATING: "AUXILIARY_HEATING",
    Capability.FUEL_STATUS: "FUEL_STATUS",
}


def extract_vehicle_capabilities(
    data: dict[str, Any], errors: Sequence[VehicleError] = ()
) -> set[Capability]:
    """Extract the set of supported capabilities from a vehicle data dump."""
    caps: set[Capability] = set()
    unavailable = {
        error.type.rsplit("_", 1)[0]
        for error in errors
        if error.type.endswith("_UNAVAILABLE")
    }

    def supported(capability: Capability, present: bool) -> bool:
        prefix = _TRANSIENT_ERROR_PREFIXES.get(capability)
        return present or (prefix is not None and prefix in unavailable)

    # Basic objects
    status = data.get("status")
    if supported(Capability.STATUS, bool(status)):
        caps.add(Capability.STATUS)
        detail = (status or {}).get("detail")
        if detail and detail.get("sunroof"):
            caps.add(Capability.SUNROOF)
    if supported(Capability.ODOMETER, bool(data.get("odometer"))):
        caps.add(Capability.ODOMETER)
    if supported(Capability.POSITION, bool(data.get("parking_position"))):
        caps.add(Capability.POSITION)
    if supported(Capability.CHARGING, bool(data.get("charging"))):
        caps.add(Capability.CHARGING)
    if data.get("charging_profiles"):
        caps.add(Capability.CHARGING_PROFILES)
    if supported(Capability.AIR_CONDITIONING, bool(data.get("air_conditioning"))):
        caps.add(Capability.AIR_CONDITIONING)
    if supported(Capability.AUXILIARY_HEATING, bool(data.get("auxiliary_heating"))):
        caps.add(Capability.AUXILIARY_HEATING)
    if supported(Capability.VENTILATION, bool(data.get("active_ventilation"))):
        caps.add(Capability.VENTILATION)
    if supported(Capability.FUEL_STATUS, bool(data.get("fuel_status"))):
        caps.add(Capability.FUEL_STATUS)
    if data.get("ad_blue_range"):
        caps.add(Capability.ADBLUE)

    # Fuel
    range_info = data.get("fuel_status") or {}
    if range_info:
        primary_engine = range_info.get("primary_engine_range") or range_info.get(
            "primaryEngineRange"
        )
        secondary_engine = range_info.get("secondary_engine_range") or range_info.get(
            "secondaryEngineRange"
        )
        engine_type_primary = (
            primary_engine.get("engine_type") or primary_engine.get("engineType")
            if isinstance(primary_engine, dict)
            else getattr(primary_engine, "engine_type", None)
            or getattr(primary_engine, "engineType", None)
        )
        engine_type_secondary = (
            secondary_engine.get("engine_type") or secondary_engine.get("engineType")
            if isinstance(secondary_engine, dict)
            else getattr(secondary_engine, "engine_type", None)
            or getattr(secondary_engine, "engineType", None)
        )
        primary_str = (engine_type_primary or "").upper()
        secondary_str = (engine_type_secondary or "").upper()
        if "ELECTRIC" in (primary_str, secondary_str):
            caps.add(Capability.CT_ELECTRIC)
        if range_info.get("car_type") is not None:
            car_type = range_info.get("car_type")
            if car_type == "HYBRID":
                caps.add(Capability.CT_HYBRID)
            if car_type == "GASOLINE":
                caps.add(Capability.CT_GASOLINE)
            if car_type == "DIESEL":
                caps.add(Capability.CT_DIESEL)
            if car_type == "CNG":
                caps.add(Capability.CT_CNG)
            if car_type == "LPG":
                caps.add(Capability.CT_LPG)
        if range_info.get("ad_blue_range") is not None:
            caps.add(Capability.ADBLUE)

    return caps


class CapabilitySelector:
    """Class to select which entities will be added to Home Assistant based on vehicle capabilities."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle_data: Any,
        errors: Sequence[VehicleError] = (),
    ) -> None:
        """Extract the vehicle capabilities from the provided data."""
        self.hass = hass

        if hasattr(vehicle_data, "model_dump"):
            raw_data = vehicle_data.model_dump(by_alias=False)
        elif hasattr(vehicle_data, "dict"):
            raw_data = vehicle_data.dict()
        elif isinstance(vehicle_data, dict):
            raw_data = vehicle_data
        else:
            raw_data = {}

        vin = getattr(vehicle_data, "vin", None)

        self.car_capabilities: set[Capability] = extract_vehicle_capabilities(
            raw_data, errors
        )
        _LOGGER.debug("[%s] CAPABILITIES: %s", vin, self.car_capabilities)
        self.entities: list[Entity] = []

    def _evaluate_capabilities(self, req: Any) -> bool:
        """Evaluate if required capabilities match vehicle capabilities (supports AND/OR)."""
        if not req:
            return True

        # Alone capabilities
        if isinstance(req, (Capability, str)):
            return req in self.car_capabilities

        # Inner structure
        if isinstance(req, (list, set, tuple)):
            for item in req:
                # Item is a group -> logic OR (one of them is enough)
                if isinstance(item, (list, set, tuple)):
                    if not any(sub_cap in self.car_capabilities for sub_cap in item):
                        return False
                # Item is an alone capability -> logic AND (vehicle has to have all)
                elif isinstance(item, (Capability, str)):
                    if item not in self.car_capabilities:
                        return False
            return True

        return False

    def add_entity(
        self,
        entity_cls: Callable[[SkodaUpdateCoordinator], Entity],
        coordinator: SkodaUpdateCoordinator,
    ) -> None:
        """Add an entity if the vehicle matches required capability logic."""
        raw_capabilities = getattr(entity_cls, "capabilities", None)

        if callable(raw_capabilities):
            try:
                required_caps = raw_capabilities()
            except (TypeError, ValueError) as err:
                _LOGGER.error(
                    "Error evaluating capabilities for %s: %s",
                    entity_cls.__name__,
                    err,
                )
                required_caps = None
        else:
            required_caps = raw_capabilities

        if self._evaluate_capabilities(required_caps):
            self.entities.append(entity_cls(coordinator))
        else:
            _LOGGER.debug(
                "Entity %s skipped. Requirements %s do not match vehicle capabilities: %s",
                entity_cls.__name__,
                required_caps,
                self.car_capabilities,
            )

    def get_entities(self) -> list[Entity]:
        """Return the list of entities selected for the vehicle."""
        return self.entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda sensors from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    if coordinator.data and coordinator.data.vehicle_response:
        vehicle_data = coordinator.data.vehicle_response.vehicle
        errors = coordinator.data.vehicle_response.errors
    else:
        vehicle_data = None
        errors = ()

    selector = CapabilitySelector(hass, vehicle_data, errors)

    selector.add_entity(MileAge, coordinator)
    selector.add_entity(LastSynchronization, coordinator)
    selector.add_entity(FuelLevel, coordinator)
    selector.add_entity(BatteryPercentage, coordinator)
    selector.add_entity(TotalRange, coordinator)
    selector.add_entity(ElectricRange, coordinator)
    selector.add_entity(RemainingACTime, coordinator)
    selector.add_entity(ChargingPowerInKw, coordinator)
    selector.add_entity(ChargingStateSensor, coordinator)
    selector.add_entity(RemainingTimeToFullCharge, coordinator)
    selector.add_entity(ChargeTypeSensor, coordinator)
    selector.add_entity(AuxiliaryHeatingMode, coordinator)
    selector.add_entity(AuxHeatingDuration, coordinator)
    selector.add_entity(PresetTemperatureValue, coordinator)
    selector.add_entity(APIKeyExpiration, coordinator)
    selector.add_entity(RateLimitRemaining, coordinator)
    selector.add_entity(RateLimitResetSeconds, coordinator)
    selector.add_entity(NextUpdateInterval, coordinator)
    selector.add_entity(LicencePlate, coordinator)

    async_add_entities(selector.get_entities())


class SkodaSensor(SkodaEntity, SensorEntity):
    """Base class for all Škoda sensor entities."""

    def __init__(self, coordinator: SkodaUpdateCoordinator) -> None:
        """Initialize the sensor with a coordinator and VIN."""
        vin = coordinator.vin
        super().__init__(coordinator, vin)


class MileAge(SkodaSensor):
    """Vehicle total kms driven."""

    entity_description = SensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-info",
    )

    @property
    @override
    def native_value(self) -> int | None:
        odometer = self.open_api_odometer
        if odometer and odometer.mileage_in_km is not None:
            return odometer.mileage_in_km

        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.ODOMETER]


class LastSynchronization(SkodaSensor):
    """Last synchronization of data on the server."""

    entity_description = SensorEntityDescription(
        key="timestamp_last_sync",
        translation_key="timestamp_last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-sync-outline",
    )

    @property
    @override
    def native_value(self) -> datetime | None:
        status = self.open_api_vehicle_status
        if status is not None and status.car_captured_timestamp:
            timestamp_str = status.car_captured_timestamp
            if isinstance(timestamp_str, str):
                return datetime.fromisoformat(timestamp_str)
            return timestamp_str
        return None


class FuelLevel(SkodaSensor):
    """Fuel level of an non-electric vehicles."""

    entity_description = SensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gas-station",
    )

    @property
    @override
    def native_value(self) -> int | None:
        driving_range = self.open_api_driving_range
        if driving_range is not None:
            # Display primary engine range
            primary_engine = driving_range.primary_engine_range
            if (
                primary_engine is not None
                and primary_engine.current_fuel_level_in_percent is not None
            ):
                return primary_engine.current_fuel_level_in_percent

            # Display secondary engine range
            secondary_engine = driving_range.secondary_engine_range
            if secondary_engine is not None:
                return secondary_engine.current_fuel_level_in_percent

        return None

    @staticmethod
    def capabilities() -> list[Any]:
        """Return the capabilities required for this entity.

        Requires a combustion-capable car type in addition to FUEL_STATUS,
        since an electric vehicle also reports FUEL_STATUS but never a fuel
        level, which would otherwise create a permanently unknown entity.
        """
        return [
            Capability.FUEL_STATUS,
            [
                Capability.CT_GASOLINE,
                Capability.CT_DIESEL,
                Capability.CT_HYBRID,
                Capability.CT_CNG,
                Capability.CT_LPG,
            ],
        ]


class BatteryPercentage(SkodaSensor):
    """Battery percentage level - only for electric and hybrid vehicles."""

    entity_description = SensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
    )

    @property
    @override
    def native_value(self) -> int | None:
        charging = self.open_api_charging
        if (
            charging is not None
            and charging.status is not None
            and charging.status.battery is not None
        ):
            return charging.status.battery.state_of_charge_in_percent
        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class TotalRange(SkodaSensor):
    """Total range of the vehicle."""

    entity_description = SensorEntityDescription(
        key="remaining_range",
        translation_key="total_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control",
    )

    @property
    @override
    def native_value(self) -> int | float | None:
        driving_range = self.open_api_driving_range
        if driving_range is not None:
            return driving_range.total_range_in_km
        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.FUEL_STATUS]


class ElectricRange(SkodaSensor):
    """electric range of the vehicle."""

    entity_description = SensorEntityDescription(
        key="remaining_electric_range",
        translation_key="electric_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control",
    )

    @property
    @override
    def native_value(self) -> int | float | None:
        charging = self.open_api_charging
        if (
            charging is not None
            and charging.status is not None
            and charging.status.battery is not None
            and charging.status.battery.remaining_cruising_range_in_meters is not None
        ):
            return charging.status.battery.remaining_cruising_range_in_meters / 1000

        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class RemainingACTime(SkodaSensor):
    """Remaining time of the AC."""

    entity_description = SensorEntityDescription(
        key="remaining_ac_time",
        translation_key="remaining_ac_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-digital",
    )

    @property
    @override
    def native_value(self) -> datetime | None:
        ac = self.open_api_air_conditioning
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

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.AIR_CONDITIONING]


class ChargingPowerInKw(SkodaSensor):
    """Sensor for charging power in Kw."""

    entity_description = SensorEntityDescription(
        key="charging_power",
        translation_key="charging_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    )

    @property
    @override
    def native_value(self) -> float | None:
        charging = self.open_api_charging
        if not charging or not charging.status:
            return None

        if charging.status.state != ChargingState.CHARGING:
            return None

        return charging.status.charge_power_in_kw

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class ChargingStateSensor(SkodaSensor):
    """Sensor for charging power in Kw."""

    entity_description = SensorEntityDescription(
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
    )

    _STATE_MAP = {
        ChargingState.CHARGING: "charging",
        ChargingState.CONNECT_CABLE: "connect_cable",
        ChargingState.READY_FOR_CHARGING: "ready_for_charging",
        ChargingState.CONSERVING: "conserving",
        ChargingState.DISCHARGING: "discharging",
        ChargingState.CHARGING_INTERRUPTED: "charging_interrupted",
    }

    @property
    @override
    def native_value(self) -> str | None:
        charging = self.open_api_charging
        if not charging or not charging.status:
            return None

        return self._STATE_MAP.get(charging.status.state)

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class RemainingTimeToFullCharge(SkodaSensor):
    """RemainingTime to fully charge battery."""

    entity_description = SensorEntityDescription(
        key="remaining_time_to_full_battery",
        translation_key="remaining_time_to_full_battery",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:battery-charging-medium",
    )

    @property
    @override
    def native_value(self) -> float | None:
        charging = self.open_api_charging
        if not charging or not charging.status:
            return None

        if charging.status.state != ChargingState.CHARGING:
            return None

        return charging.status.remaining_time_to_fully_charged_in_minutes

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class ChargeTypeSensor(SkodaSensor):
    """Charge type - AC/DC/OFF."""

    entity_description = SensorEntityDescription(
        key="charge_type",
        translation_key="charge_type",
        device_class=SensorDeviceClass.ENUM,
        options=["ac", "dc", "off", "not_charging"],
        icon="mdi:connection",
    )

    _CHARGE_TYPE_MAP = {
        ChargeType.AC: "ac",
        ChargeType.DC: "dc",
        ChargeType.OFF: "off",
    }

    @property
    @override
    def native_value(self) -> str | None:
        charging = self.open_api_charging
        if (
            not charging
            or not charging.status
            or not charging.status.charge_type
            or not charging.status.state
        ):
            return None

        if charging.status.state != ChargingState.CHARGING:
            return "not_charging"

        return self._CHARGE_TYPE_MAP.get(charging.status.charge_type)

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.CHARGING]


class AuxiliaryHeatingMode(SkodaSensor):
    """Entity that returns the Mode of Auxiliary heating."""

    entity_description = SensorEntityDescription(
        key="auxiliary_heating_mode",
        translation_key="auxiliary_heating_mode",
        icon="mdi:heating-coil",
    )

    @property
    @override
    def native_value(self) -> str | None:
        aux_heat = self.open_api_auxiliary_heating

        if aux_heat is not None and aux_heat.start_mode is not None:
            val = getattr(aux_heat.start_mode, "value", aux_heat.start_mode)
            return str(val) if val is not None else None

        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.AUXILIARY_HEATING]


class AuxHeatingDuration(SkodaSensor):
    """Entity that returns the remaining time of active Heating in seconds."""

    entity_description = SensorEntityDescription(
        key="aux_heating_duration",
        translation_key="aux_heating_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:fan-clock",
    )

    @property
    @override
    def native_value(self) -> int | None:
        aux_heat = self.open_api_auxiliary_heating

        if aux_heat is not None:
            return aux_heat.duration_in_seconds

        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.AUXILIARY_HEATING]


class PresetTemperatureValue(SkodaSensor):
    """Preset target cabin temperature."""

    entity_description = SensorEntityDescription(
        key="preset_temperature_value",
        translation_key="preset_temperature_value",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
    )

    @property
    @override
    def native_unit_of_measurement(self) -> str:
        ac = self.open_api_air_conditioning
        if (
            ac
            and ac.target_temperature
            and ac.target_temperature.unit == TemperatureUnit.FAHRENHEIT
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    @override
    def native_value(self) -> float | None:
        ac = self.open_api_air_conditioning
        if not ac or ac.target_temperature is None:
            return None

        return ac.target_temperature.value

    @staticmethod
    def capabilities() -> list[Capability]:
        """Return the capabilities required for this entity."""
        return [Capability.AIR_CONDITIONING]


class APIKeyExpiration(SkodaSensor):
    """API key expiration timestamp."""

    entity_description = SensorEntityDescription(
        key="api_key_expiration",
        translation_key="api_key_expiration",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:api",
    )

    @property
    @override
    def native_value(self) -> datetime | None:
        if not self.api_key_expires_at:
            return None
        try:
            return datetime.fromisoformat(self.api_key_expires_at)
        except ValueError:
            return None


class RateLimitRemaining(SkodaSensor):
    """Number of API requests remaining in the current window."""

    entity_description = SensorEntityDescription(
        key="rate_limit_remaining",
        translation_key="rate_limit_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:counter",
    )

    @property
    @override
    def native_value(self) -> int | None:
        return self.rate_limit_remaining


class RateLimitResetSeconds(SkodaSensor):
    """Timestamp when the API rate limit resets."""

    entity_description = SensorEntityDescription(
        key="rate_limit_reset_seconds",
        translation_key="rate_limit_reset_seconds",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:timelapse",
    )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the calculated UTC datetime of the rate limit reset."""
        return self.coordinator.rate_limit_reset_time


class NextUpdateInterval(SkodaSensor):
    """Timestamp of the next coordinator update."""

    entity_description = SensorEntityDescription(
        key="next_update_interval",
        translation_key="next_update_interval",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:timer-sync-outline",
    )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return next expected refresh datetime in UTC."""
        return self.coordinator.next_update_time


class LicencePlate(SkodaSensor):
    """Sensor for registration plate of the vehicle."""

    entity_description = SensorEntityDescription(
        key="licence_plate",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alpha-r-box-outline",
        translation_key="licence_plate",
    )

    @property
    @override
    def native_value(self) -> str | None:
        oa_vehicle = self.open_api_vehicle
        if oa_vehicle and oa_vehicle.license_plate:
            return oa_vehicle.license_plate

        return None
