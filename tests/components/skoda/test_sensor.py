"""Test the Škoda sensor platform."""

from datetime import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from skoda_public_api.models.enums import (
    AirConditioningState,
    AuxiliaryHeatingStartMode,
    AuxiliaryHeatingState,
    ChargeType,
    ChargingState,
    TemperatureUnit,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.skoda.coordinator import SkodaUpdateCoordinator
from homeassistant.components.skoda.sensor import (
    SENSOR_TYPES,
    SkodaSensor,
    SkodaSensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, snapshot_platform

VIN = "TMBJM7NP2M1TMP511"


def _description(key: str) -> SkodaSensorEntityDescription:
    """Look up a sensor's entity description by key."""
    return next(description for description in SENSOR_TYPES if description.key == key)


def _make_vehicle_coordinator(vehicle: SimpleNamespace) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given vehicle object."""
    vehicle_response = SimpleNamespace(vehicle=vehicle)
    data = SimpleNamespace(vehicle_response=vehicle_response)
    return cast(SkodaUpdateCoordinator, SimpleNamespace(vin=VIN, data=data))


def _make_odometer_coordinator(
    odometer: SimpleNamespace | None,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given odometer."""
    return _make_vehicle_coordinator(SimpleNamespace(odometer=odometer, name=None))


def _make_fuel_status_coordinator(
    fuel_status: SimpleNamespace | None,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given fuel_status."""
    return _make_vehicle_coordinator(
        SimpleNamespace(fuel_status=fuel_status, name=None)
    )


def _make_air_conditioning_coordinator(
    air_conditioning: SimpleNamespace,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given air_conditioning."""
    return _make_vehicle_coordinator(
        SimpleNamespace(air_conditioning=air_conditioning, name=None)
    )


def _make_charging_coordinator(
    charging: SimpleNamespace | None,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given charging status."""
    return _make_vehicle_coordinator(SimpleNamespace(charging=charging, name=None))


def _make_vehicle_status_coordinator(status: SimpleNamespace) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given vehicle status."""
    return _make_vehicle_coordinator(SimpleNamespace(status=status, name=None))


def _make_auxiliary_heating_coordinator(
    auxiliary_heating: SimpleNamespace | None,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given auxiliary_heating."""
    return _make_vehicle_coordinator(
        SimpleNamespace(auxiliary_heating=auxiliary_heating, name=None)
    )


def test_fuel_level_falls_back_to_secondary_engine() -> None:
    """A hybrid with an electric primary engine still reports the combustion engine's fuel level."""
    fuel_status = SimpleNamespace(
        primary_engine_range=SimpleNamespace(current_fuel_level_in_percent=None),
        secondary_engine_range=SimpleNamespace(current_fuel_level_in_percent=42),
    )
    coordinator = _make_fuel_status_coordinator(fuel_status)
    sensor = SkodaSensor(coordinator, _description("fuel_level"))

    assert sensor.native_value == 42


def test_fuel_level_prefers_primary_engine_when_available() -> None:
    """The primary engine's fuel level is used whenever it is actually reported."""
    fuel_status = SimpleNamespace(
        primary_engine_range=SimpleNamespace(current_fuel_level_in_percent=77),
        secondary_engine_range=SimpleNamespace(current_fuel_level_in_percent=42),
    )
    coordinator = _make_fuel_status_coordinator(fuel_status)
    sensor = SkodaSensor(coordinator, _description("fuel_level"))

    assert sensor.native_value == 77


def test_fuel_level_returns_none_without_any_engine_data() -> None:
    """No fuel level is reported when neither engine reports a fuel level at all."""
    fuel_status = SimpleNamespace(
        primary_engine_range=SimpleNamespace(current_fuel_level_in_percent=None),
        secondary_engine_range=None,
    )
    coordinator = _make_fuel_status_coordinator(fuel_status)
    sensor = SkodaSensor(coordinator, _description("fuel_level"))

    assert sensor.native_value is None


def test_mileage_returns_none_without_odometer() -> None:
    """No mileage is reported when the vehicle has no odometer data."""
    coordinator = _make_odometer_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("mileage"))

    assert sensor.native_value is None


def test_fuel_level_returns_none_without_driving_range() -> None:
    """No fuel level is reported when the vehicle has no fuel status data."""
    coordinator = _make_fuel_status_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("fuel_level"))

    assert sensor.native_value is None


def test_total_range_returns_none_without_driving_range() -> None:
    """No total range is reported when the vehicle has no fuel status data."""
    coordinator = _make_fuel_status_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("remaining_range"))

    assert sensor.native_value is None


def test_battery_percentage_returns_none_without_battery() -> None:
    """No battery percentage is reported when charging status has no battery data."""
    charging = SimpleNamespace(status=SimpleNamespace(battery=None))
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("battery_percentage"))

    assert sensor.native_value is None


def test_electric_range_returns_none_without_battery() -> None:
    """No electric range is reported when charging status has no battery data."""
    charging = SimpleNamespace(status=SimpleNamespace(battery=None))
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("remaining_electric_range"))

    assert sensor.native_value is None


def test_auxiliary_heating_mode_maps_start_mode() -> None:
    """The auxiliary heating mode sensor reports the mapped start mode."""
    auxiliary_heating = SimpleNamespace(start_mode=AuxiliaryHeatingStartMode.HEATING)
    coordinator = _make_auxiliary_heating_coordinator(auxiliary_heating)
    sensor = SkodaSensor(coordinator, _description("auxiliary_heating_mode"))

    assert sensor.native_value == "heating"


def test_aux_heating_duration_returns_none_without_auxiliary_heating() -> None:
    """No auxiliary heating duration is reported without auxiliary heating data."""
    coordinator = _make_auxiliary_heating_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("aux_heating_duration"))

    assert sensor.native_value is None


def test_aux_heating_duration_returns_none_when_off() -> None:
    """No remaining duration is reported while auxiliary heating isn't running."""
    auxiliary_heating = SimpleNamespace(
        state=AuxiliaryHeatingState.OFF, duration_in_seconds=1200
    )
    coordinator = _make_auxiliary_heating_coordinator(auxiliary_heating)
    sensor = SkodaSensor(coordinator, _description("aux_heating_duration"))

    assert sensor.native_value is None


def test_aux_heating_duration_reports_remaining_time_while_heating() -> None:
    """The remaining duration is reported while auxiliary heating is active."""
    auxiliary_heating = SimpleNamespace(
        state=AuxiliaryHeatingState.HEATING, duration_in_seconds=1200
    )
    coordinator = _make_auxiliary_heating_coordinator(auxiliary_heating)
    sensor = SkodaSensor(coordinator, _description("aux_heating_duration"))

    assert sensor.native_value == 1200


def test_licence_plate_returns_none_without_license_plate() -> None:
    """No registration plate is reported when the API doesn't provide one."""
    vehicle = SimpleNamespace(license_plate=None, name=None)
    coordinator = _make_vehicle_coordinator(vehicle)
    sensor = SkodaSensor(coordinator, _description("licence_plate"))

    assert sensor.native_value is None


def test_preset_temperature_defaults_to_celsius() -> None:
    """Without an explicit unit (or Celsius), the entity reports Celsius."""
    air_conditioning = SimpleNamespace(
        target_temperature=SimpleNamespace(value=21.5, unit=TemperatureUnit.CELSIUS)
    )
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("preset_temperature_value"))

    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.native_value == 21.5


def test_preset_temperature_reports_fahrenheit_when_api_does() -> None:
    """A Fahrenheit reading from the API must not be mislabeled as Celsius."""
    air_conditioning = SimpleNamespace(
        target_temperature=SimpleNamespace(value=72.0, unit=TemperatureUnit.FAHRENHEIT)
    )
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("preset_temperature_value"))

    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert sensor.native_value == 72.0


def test_preset_temperature_handles_missing_target_temperature() -> None:
    """Air conditioning present without a target temperature must not raise."""
    air_conditioning = SimpleNamespace(target_temperature=None)
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("preset_temperature_value"))

    assert sensor.native_value is None


def test_remaining_ac_time_parses_datetime_target() -> None:
    """A target timestamp already provided as a datetime is converted to UTC as-is."""
    target = datetime(2024, 1, 10, 12, 30, 0)
    air_conditioning = SimpleNamespace(
        state=AirConditioningState.COOLING,
        estimated_reach_of_target_temperature_at=target,
    )
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("remaining_ac_time"))

    assert sensor.native_value == dt_util.as_utc(target)


def test_remaining_ac_time_parses_string_target() -> None:
    """A target timestamp provided as a string is parsed and converted to UTC."""
    air_conditioning = SimpleNamespace(
        state=AirConditioningState.COOLING,
        estimated_reach_of_target_temperature_at="2024-01-10T12:30:00+00:00",
    )
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("remaining_ac_time"))
    expected = dt_util.parse_datetime("2024-01-10T12:30:00+00:00")
    assert expected is not None

    assert sensor.native_value == dt_util.as_utc(expected)


def test_remaining_ac_time_returns_none_without_target_timestamp() -> None:
    """No AC remaining time is reported when the API doesn't provide a target timestamp."""
    air_conditioning = SimpleNamespace(
        state=AirConditioningState.COOLING,
        estimated_reach_of_target_temperature_at=None,
    )
    coordinator = _make_air_conditioning_coordinator(air_conditioning)
    sensor = SkodaSensor(coordinator, _description("remaining_ac_time"))

    assert sensor.native_value is None


def test_last_synchronization_parses_string_timestamp() -> None:
    """A string timestamp from the API is parsed into a timezone-aware UTC datetime."""
    status = SimpleNamespace(car_captured_timestamp="2024-01-10T10:00:00+00:00")
    coordinator = _make_vehicle_status_coordinator(status)
    sensor = SkodaSensor(coordinator, _description("timestamp_last_sync"))

    assert sensor.native_value == dt_util.as_utc(
        datetime.fromisoformat("2024-01-10T10:00:00+00:00")
    )


def test_last_synchronization_converts_naive_timestamp_object_to_utc() -> None:
    """A timestamp that is already a datetime object is still normalized to UTC."""
    timestamp = datetime(2024, 1, 10, 10, 0, 0)
    status = SimpleNamespace(car_captured_timestamp=timestamp)
    coordinator = _make_vehicle_status_coordinator(status)
    sensor = SkodaSensor(coordinator, _description("timestamp_last_sync"))

    native_value = sensor.native_value
    assert isinstance(native_value, datetime)
    assert native_value == dt_util.as_utc(timestamp)
    assert native_value.tzinfo is not None


def test_charging_power_returns_none_when_not_charging() -> None:
    """No charging power is reported while the vehicle isn't actively charging."""
    charging = SimpleNamespace(
        status=SimpleNamespace(state=ChargingState.CONSERVING, charge_power_in_kw=5.0)
    )
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("charging_power"))

    assert sensor.native_value is None


def test_remaining_time_to_full_charge_returns_none_when_not_charging() -> None:
    """No remaining-to-full time is reported while the vehicle isn't actively charging."""
    charging = SimpleNamespace(
        status=SimpleNamespace(
            state=ChargingState.CONSERVING,
            remaining_time_to_fully_charged_in_minutes=30,
        )
    )
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("remaining_time_to_full_battery"))

    assert sensor.native_value is None


def test_charge_type_reports_not_charging_when_not_charging() -> None:
    """The charge type sensor reports 'not_charging' while the vehicle isn't charging."""
    charging = SimpleNamespace(
        status=SimpleNamespace(
            state=ChargingState.CONSERVING, charge_type=ChargeType.AC
        )
    )
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("charge_type"))

    assert sensor.native_value == "not_charging"


def test_charge_type_returns_none_without_charging() -> None:
    """No charge type is reported when the vehicle has no charging data at all."""
    coordinator = _make_charging_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("charge_type"))

    assert sensor.native_value is None


def test_charge_type_reports_not_charging_without_charge_type() -> None:
    """A vehicle that isn't charging reports 'not_charging' even if no charge type is sent."""
    charging = SimpleNamespace(
        status=SimpleNamespace(state=ChargingState.CONSERVING, charge_type=None)
    )
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("charge_type"))

    assert sensor.native_value == "not_charging"


def test_charging_state_returns_none_without_status() -> None:
    """Charging present without a status sub-object must not raise."""
    charging = SimpleNamespace(status=None)
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("charging_state"))

    assert sensor.native_value is None


def test_charging_power_returns_none_without_charging() -> None:
    """No charging power is reported when the vehicle has no charging data at all."""
    coordinator = _make_charging_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("charging_power"))

    assert sensor.native_value is None


def test_remaining_time_to_full_charge_returns_none_without_charging() -> None:
    """No remaining-to-full time is reported when the vehicle has no charging data at all."""
    coordinator = _make_charging_coordinator(None)
    sensor = SkodaSensor(coordinator, _description("remaining_time_to_full_battery"))

    assert sensor.native_value is None


def test_charge_type_returns_none_without_charge_type() -> None:
    """No charge type is reported when the API doesn't provide one."""
    charging = SimpleNamespace(
        status=SimpleNamespace(state=ChargingState.CHARGING, charge_type=None)
    )
    coordinator = _make_charging_coordinator(charging)
    sensor = SkodaSensor(coordinator, _description("charge_type"))

    assert sensor.native_value is None


def test_is_supported_returns_false_when_capability_missing() -> None:
    """A sensor is not selected when the vehicle lacks its required capability."""
    description = _description("mileage")

    assert description.is_supported(set()) is False


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda sensor entities against a snapshot."""
    freezer.move_to("2024-01-10T12:00:00+00:00")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
