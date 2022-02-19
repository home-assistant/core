"""Fixtures for Google Time Travel tests."""
from unittest.mock import patch

from googlemaps.exceptions import ApiError
import pytest


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture():
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="bypass_platform_setup")
def bypass_platform_setup_fixture():
    """Bypass platform setup."""
    with patch(
        "homeassistant.components.google_travel_time.sensor.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture():
    """Return valid config entry."""
    with patch("homeassistant.components.google_travel_time.helpers.Client"), patch(
        "homeassistant.components.google_travel_time.helpers.distance_matrix"
    ) as distance_matrix_mock:
        distance_matrix_mock.return_value = None
        yield distance_matrix_mock


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry):
    """Return invalid config entry."""
    validate_config_entry.side_effect = ApiError("test")
