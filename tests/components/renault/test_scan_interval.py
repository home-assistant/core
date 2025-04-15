"""Tests for Renault scan interval."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from renault_api.kamereon.exceptions import AccessDeniedException, NotSupportedException

from homeassistant.components.renault.const import MAX_CALLS_PER_HOURS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import _get_fixtures, patch_get_vehicle_data

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> None:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    ("vehicle_type", "expected_coordinator_count", "expected_scan_interval"),
    [
        # One vehicle with 5 coordinators
        ("zoe_40", 5, timedelta(seconds=(3600 * 5) / MAX_CALLS_PER_HOURS)),
        # One vehicle with partial coordinators
        ("captur_fuel", 4, timedelta(seconds=(3600 * 4) / MAX_CALLS_PER_HOURS)),
    ],
)
async def test_scan_interval_calculation_single_vehicle(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    vehicle_type: str,
    expected_coordinator_count: int,
    expected_scan_interval: timedelta,
) -> None:
    """Test the scan interval is properly calculated for a single vehicle."""
    # Set up fixtures for the vehicle
    mock_fixtures = _get_fixtures(vehicle_type)

    with patch_get_vehicle_data() as patches:
        # Set up the fixtures
        for key, value in patches.items():
            value.return_value = mock_fixtures[key]

        # Setup the component
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify that the vehicle has the expected number of coordinators
        vehicle = list(config_entry.runtime_data.vehicles.values())[0]
        assert len(vehicle.coordinators) == expected_coordinator_count

        # Verify scan interval
        assert vehicle._scan_interval == expected_scan_interval

        # Check that all coordinators have the correct interval
        for coordinator in vehicle.coordinators.values():
            assert coordinator.update_interval == expected_scan_interval


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_scan_interval_update_on_coordinator_removal(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the scan interval is recalculated when coordinators are removed."""

    # Expected coordinators after removal
    final_count = 2  # After removing some coordinators

    # Fixture with some endpoints failing
    mock_fixtures = _get_fixtures("zoe_40")

    with patch_get_vehicle_data() as patches:
        # Set up fixtures with some endpoints failing
        # First add all normal endpoints
        for key, value in patches.items():
            value.return_value = mock_fixtures[key]

        # Make battery_status, charge_mode, lock_status, and res_state fail
        not_supported_exception = NotSupportedException(
            "err.tech.501",
            "This feature is not technically supported by this gateway",
        )

        access_denied_exception = AccessDeniedException(
            "err.func.403",
            "Access is denied for this resource",
        )

        # Override with exceptions for some endpoints
        patches["battery_status"].side_effect = not_supported_exception
        patches["charge_mode"].side_effect = not_supported_exception
        patches["lock_status"].side_effect = access_denied_exception
        patches["res_state"].side_effect = access_denied_exception

        # Setup the component
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the vehicle has the correct number of coordinators after failures
        vehicle = list(config_entry.runtime_data.vehicles.values())[0]
        assert len(vehicle.coordinators) == final_count

        # Calculate the expected scan interval
        expected_scan_interval = timedelta(
            seconds=(3600 * final_count) / MAX_CALLS_PER_HOURS
        )

        # Verify scan interval
        assert vehicle._scan_interval == expected_scan_interval

        # Check that all coordinators have the correct interval
        for coordinator in vehicle.coordinators.values():
            assert coordinator.update_interval == expected_scan_interval
