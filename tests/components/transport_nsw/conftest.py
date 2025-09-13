"""Common fixtures for the Transport NSW tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.transport_nsw.const import DOMAIN, SUBENTRY_TYPE_STOP
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_transport_nsw_api() -> Generator[AsyncMock]:
    """Mock the TransportNSW API."""
    with patch("TransportNSW.TransportNSW") as mock_api:
        mock_instance = AsyncMock()
        mock_api.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_config_entry_legacy():
    """Mock legacy config entry for migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            "stop_id": "test_stop_id",
            CONF_NAME: "Test Stop",
            "route": "",
            "destination": "",
        },
        unique_id="test_stop_id",
    )


@pytest.fixture
def mock_config_entry_with_subentries():
    """Mock config entry with subentries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        title="Transport NSW",
    )

    # Add subentries
    subentry1 = ConfigSubentry(
        data={
            "stop_id": "stop_001",
            CONF_NAME: "Central Station",
            "route": "",
            "destination": "",
        },
        subentry_id="subentry_1",
        subentry_type=SUBENTRY_TYPE_STOP,
        title="Central Station",
        unique_id="test_entry_stop_001",
    )

    subentry2 = ConfigSubentry(
        data={
            "stop_id": "stop_002",
            CONF_NAME: "Town Hall",
            "route": "T1",
            "destination": "Hornsby",
        },
        subentry_id="subentry_2",
        subentry_type=SUBENTRY_TYPE_STOP,
        title="Town Hall",
        unique_id="test_entry_stop_002",
    )

    entry.subentries = {
        "subentry_1": subentry1,
        "subentry_2": subentry2,
    }

    return entry


@pytest.fixture
def mock_subentry_data():
    """Mock subentry data for testing."""
    return {
        "stop_id": "test_stop_id",
        CONF_NAME: "Test Stop",
        "route": "T1",
        "destination": "Test Destination",
    }


@pytest.fixture
def mock_transport_nsw_api_error():
    """Mock TransportNSW API with error responses."""
    with patch("TransportNSW.TransportNSW") as mock_api:
        mock_instance = AsyncMock()
        mock_instance.get_departures.side_effect = Exception("API Error")
        mock_api.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock successful API response."""
    return {
        "route": "Test Route",
        "due": 5,
        "delay": 0,
        "real_time": True,
        "destination": "Test Destination",
        "mode": "Bus",
    }


@pytest.fixture
def mock_api_response_with_nulls():
    """Mock API response with None and n/a values."""
    return {
        "route": None,
        "due": "n/a",
        "delay": 0,
        "real_time": True,
        "destination": None,
        "mode": "Bus",
    }
