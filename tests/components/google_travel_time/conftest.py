"""Fixtures for Google Time Travel tests."""
from unittest.mock import Mock, patch

from googlemaps.exceptions import ApiError
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
        "homeassistant.components.google_travel_time.helpers.Client",
        return_value=Mock(),
    ), patch(
        "homeassistant.components.google_travel_time.helpers.distance_matrix",
        return_value=None,
    ):
        yield


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture():
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="bypass_update")
def bypass_update_fixture():
    """Bypass sensor update."""
    with patch("homeassistant.components.google_travel_time.sensor.distance_matrix"):
        yield


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture():
    """Return invalid config entry."""
    with patch(
        "homeassistant.components.google_travel_time.helpers.Client",
        return_value=Mock(),
    ), patch(
        "homeassistant.components.google_travel_time.helpers.distance_matrix",
        side_effect=ApiError("test"),
    ):
        yield
