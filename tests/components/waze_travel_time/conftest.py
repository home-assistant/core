"""Fixtures for Waze Travel Time tests."""
from unittest.mock import patch

from WazeRouteCalculator import WRCError
import pytest


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture():
    """Return valid config entry."""
    with patch(
        "homeassistant.components.waze_travel_time.helpers.WazeRouteCalculator"
    ) as mock_wrc:
        obj = mock_wrc.return_value
        obj.calc_all_routes_info.return_value = None
        yield


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture():
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="mock_update")
def mock_update_fixture():
    """Mock an update to the sensor."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.WazeRouteCalculator.calc_all_routes_info",
        return_value={"My route": (150, 300)},
    ):
        yield


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture():
    """Return invalid config entry."""
    with patch(
        "homeassistant.components.waze_travel_time.helpers.WazeRouteCalculator"
    ) as mock_wrc:
        obj = mock_wrc.return_value
        obj.calc_all_routes_info.return_value = {}
        obj.calc_all_routes_info.side_effect = WRCError("test")
        yield
