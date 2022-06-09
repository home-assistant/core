"""Fixtures for Waze Travel Time tests."""
from unittest.mock import patch

from WazeRouteCalculator import WRCError
import pytest


@pytest.fixture(name="mock_wrc", autouse=True)
def mock_wrc_fixture():
    """Mock out WazeRouteCalculator."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.WazeRouteCalculator"
    ) as mock_wrc:
        yield mock_wrc


@pytest.fixture(name="mock_update")
def mock_update_fixture(mock_wrc):
    """Mock an update to the sensor."""
    obj = mock_wrc.return_value
    obj.calc_all_routes_info.return_value = {"My route": (150, 300)}


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture():
    """Return valid config entry."""
    with patch(
        "homeassistant.components.waze_travel_time.helpers.WazeRouteCalculator"
    ) as mock_wrc:
        obj = mock_wrc.return_value
        obj.calc_all_routes_info.return_value = None
        yield mock_wrc


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry):
    """Return invalid config entry."""
    obj = validate_config_entry.return_value
    obj.calc_all_routes_info.return_value = {}
    obj.calc_all_routes_info.side_effect = WRCError("test")


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
