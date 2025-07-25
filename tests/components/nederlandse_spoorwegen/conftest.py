"""Fixtures for Nederlandse Spoorwegen tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen import NSRuntimeData
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_ns_api_wrapper():
    """Mock NS API wrapper."""
    wrapper = MagicMock()
    wrapper.validate_api_key = AsyncMock(return_value=True)
    wrapper.get_stations = AsyncMock(
        return_value=[
            MagicMock(code="AMS", name="Amsterdam"),
            MagicMock(code="UTR", name="Utrecht"),
        ]
    )

    # Mock the centralized normalize_station_code method
    def normalize_station_code(code):
        return code.upper() if code else ""

    wrapper.normalize_station_code = normalize_station_code

    # Mock get_station_codes method
    wrapper.get_station_codes = MagicMock(return_value={"AMS", "UTR"})

    # Create proper trip mocks with datetime objects
    future_time = datetime.now(UTC).replace(hour=23, minute=0, second=0, microsecond=0)
    mock_trips = [
        MagicMock(
            departure_time_actual=None,
            departure_time_planned=future_time,
            arrival_time="09:00",
        ),
        MagicMock(
            departure_time_actual=None,
            departure_time_planned=future_time + timedelta(minutes=30),
            arrival_time="09:30",
        ),
    ]

    wrapper.get_trips = AsyncMock(return_value=mock_trips)
    return wrapper


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )
    # runtime_data will be set when the coordinator is created
    config_entry.runtime_data = None
    return config_entry


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_ns_api_wrapper, mock_config_entry):
    """Return NSDataUpdateCoordinator instance."""
    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, mock_config_entry)
    # Set runtime_data with mock NSRuntimeData containing coordinator
    mock_config_entry.runtime_data = NSRuntimeData(coordinator=coordinator)
    return coordinator
