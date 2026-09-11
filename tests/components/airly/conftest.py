"""Fixtures for the Airly integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from airly.measurements import Measurement
import pytest

from homeassistant.components.airly.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
        unique_id="12.3-45.6",
        data={
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 12.3,
            CONF_LONGITUDE: 45.6,
        },
    )


@pytest.fixture
def mock_airly_measurements() -> Measurement:
    """Return the default mocked Airly measurements."""
    return Measurement(
        load_json_object_fixture("valid_station.json", DOMAIN)["current"]
    )


@pytest.fixture
def mock_airly_no_station_measurements() -> Measurement:
    """Return the mocked Airly measurements for an area without sensors."""
    return Measurement(load_json_object_fixture("no_station.json", DOMAIN)["current"])


@pytest.fixture
def mock_airly() -> Generator[MagicMock]:
    """Mock the Airly client class."""
    with (
        patch(
            "homeassistant.components.airly.coordinator.Airly", autospec=True
        ) as mock_airly,
        patch("homeassistant.components.airly.config_flow.Airly", new=mock_airly),
    ):
        yield mock_airly


@pytest.fixture
def mock_airly_client(
    mock_airly: MagicMock,
    mock_airly_measurements: Measurement,
) -> MagicMock:
    """Mock an Airly client instance."""
    client = mock_airly.return_value

    for measurements in (
        client.create_measurements_session_point.return_value,
        client.create_measurements_session_nearest.return_value,
    ):
        measurements.current = mock_airly_measurements
        measurements.update = AsyncMock()
    client.requests_remaining = 42
    client.requests_per_day = 100

    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Set up the Airly integration for testing."""
    await setup_integration(hass, mock_config_entry)
