"""Fixtures for Waze Travel Time tests."""
from unittest.mock import patch

import pytest
from pywaze.route_calculator import WRCError


@pytest.fixture(name="mock_update")
def mock_update_fixture():
    """Mock an update to the sensor."""
    with patch(
        "pywaze.route_calculator.WazeRouteCalculator.calc_all_routes_info",
        return_value={"My route": (150, 300)},
    ) as mock_wrc:
        yield mock_wrc


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture(mock_update):
    """Return valid config entry."""
    mock_update.return_value = None
    return mock_update


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry):
    """Return invalid config entry."""
    validate_config_entry.side_effect = WRCError("test")
    return validate_config_entry


@pytest.fixture(name="bypass_platform_setup")
def bypass_platform_setup_fixture():
    """Bypass platform setup."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture():
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield
