"""Fixtures for Google Time Travel tests."""

from unittest.mock import patch

from googlemaps.exceptions import ApiError, Timeout, TransportError
import pytest

from homeassistant.components.google_travel_time.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config")
async def mock_config_fixture(hass, data, options):
    """Mock a Google Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


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
    with (
        patch("homeassistant.components.google_travel_time.helpers.Client"),
        patch(
            "homeassistant.components.google_travel_time.helpers.distance_matrix"
        ) as distance_matrix_mock,
    ):
        distance_matrix_mock.return_value = None
        yield distance_matrix_mock


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry):
    """Return invalid config entry."""
    validate_config_entry.side_effect = ApiError("test")


@pytest.fixture(name="invalid_api_key")
def invalid_api_key_fixture(validate_config_entry):
    """Throw a REQUEST_DENIED ApiError."""
    validate_config_entry.side_effect = ApiError("REQUEST_DENIED", "Invalid API key.")


@pytest.fixture(name="timeout")
def timeout_fixture(validate_config_entry):
    """Throw a Timeout exception."""
    validate_config_entry.side_effect = Timeout()


@pytest.fixture(name="transport_error")
def transport_error_fixture(validate_config_entry):
    """Throw a TransportError exception."""
    validate_config_entry.side_effect = TransportError("Unknown.")
