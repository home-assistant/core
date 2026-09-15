"""Test the Škoda sensor platform."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from skoda_public_api.models.common import VehicleError
from skoda_public_api.models.enums import TemperatureUnit, VehicleErrorState
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.skoda.coordinator import SkodaUpdateCoordinator
from homeassistant.components.skoda.sensor import (
    Capability,
    FuelLevel,
    PresetTemperatureValue,
    extract_vehicle_capabilities,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

VIN = "TMBJM7NP2M1TMP511"


def _make_fuel_status_coordinator(
    fuel_status: SimpleNamespace,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given fuel_status."""
    vehicle = SimpleNamespace(fuel_status=fuel_status)
    vehicle_response = SimpleNamespace(vehicle=vehicle)
    data = SimpleNamespace(vehicle_response=vehicle_response)
    return cast(SkodaUpdateCoordinator, SimpleNamespace(vin=VIN, data=data))


def _make_air_conditioning_coordinator(
    air_conditioning: SimpleNamespace,
) -> SkodaUpdateCoordinator:
    """Build a minimal fake coordinator exposing the given air_conditioning."""
    vehicle = SimpleNamespace(air_conditioning=air_conditioning)
    vehicle_response = SimpleNamespace(vehicle=vehicle)
    data = SimpleNamespace(vehicle_response=vehicle_response)
    return cast(SkodaUpdateCoordinator, SimpleNamespace(vin=VIN, data=data))


def test_extract_vehicle_capabilities_keeps_transiently_unavailable_feature() -> None:
    """A feature missing only due to a transient *_UNAVAILABLE error stays supported."""
    errors = [
        VehicleError(
            type=VehicleErrorState.CHARGING_UNAVAILABLE, description="temporary"
        )
    ]

    caps = extract_vehicle_capabilities({}, errors)

    assert Capability.CHARGING in caps


def test_extract_vehicle_capabilities_drops_permanently_unsupported_feature() -> None:
    """A feature reported as *_UNSUPPORTED is not treated as supported."""
    errors = [
        VehicleError(
            type=VehicleErrorState.CHARGING_UNSUPPORTED, description="not fitted"
        )
    ]

    caps = extract_vehicle_capabilities({}, errors)

    assert Capability.CHARGING not in caps


def test_fuel_level_falls_back_to_secondary_engine() -> None:
    """A hybrid with an electric primary engine still reports the combustion engine's fuel level."""
    fuel_status = SimpleNamespace(
        primary_engine_range=SimpleNamespace(current_fuel_level_in_percent=None),
        secondary_engine_range=SimpleNamespace(current_fuel_level_in_percent=42),
    )
    sensor = FuelLevel(_make_fuel_status_coordinator(fuel_status))

    assert sensor.native_value == 42


def test_fuel_level_prefers_primary_engine_when_available() -> None:
    """The primary engine's fuel level is used whenever it is actually reported."""
    fuel_status = SimpleNamespace(
        primary_engine_range=SimpleNamespace(current_fuel_level_in_percent=77),
        secondary_engine_range=SimpleNamespace(current_fuel_level_in_percent=42),
    )
    sensor = FuelLevel(_make_fuel_status_coordinator(fuel_status))

    assert sensor.native_value == 77


def test_preset_temperature_defaults_to_celsius() -> None:
    """Without an explicit unit (or Celsius), the entity reports Celsius."""
    air_conditioning = SimpleNamespace(
        target_temperature=SimpleNamespace(value=21.5, unit=TemperatureUnit.CELSIUS)
    )
    sensor = PresetTemperatureValue(
        _make_air_conditioning_coordinator(air_conditioning)
    )

    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.native_value == 21.5


def test_preset_temperature_reports_fahrenheit_when_api_does() -> None:
    """A Fahrenheit reading from the API must not be mislabeled as Celsius."""
    air_conditioning = SimpleNamespace(
        target_temperature=SimpleNamespace(value=72.0, unit=TemperatureUnit.FAHRENHEIT)
    )
    sensor = PresetTemperatureValue(
        _make_air_conditioning_coordinator(air_conditioning)
    )

    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert sensor.native_value == 72.0


def test_preset_temperature_handles_missing_target_temperature() -> None:
    """Air conditioning present without a target temperature must not raise."""
    air_conditioning = SimpleNamespace(target_temperature=None)
    sensor = PresetTemperatureValue(
        _make_air_conditioning_coordinator(air_conditioning)
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS


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
