"""Common fixtures for the Homevolt tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from homevolt import DeviceMetadata, Sensor
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homevolt.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Homevolt",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id="40580137858664",
    )


@pytest.fixture
def mock_homevolt_client() -> Generator[MagicMock]:
    """Return a mocked Homevolt client."""
    with (
        patch(
            "homeassistant.components.homevolt.Homevolt",
            autospec=True,
        ) as homevolt_mock,
        patch(
            "homeassistant.components.homevolt.config_flow.Homevolt",
            new=homevolt_mock,
        ),
    ):
        client = homevolt_mock.return_value
        client.base_url = "http://127.0.0.1"
        client.update_info = AsyncMock()
        client.close_connection = AsyncMock()

        # Load realistic device data from fixture file
        fixture_data = json.loads(load_fixture("device_data.json", DOMAIN))

        client.unique_id = fixture_data["unique_id"]

        # Convert sensor data from JSON to Sensor objects
        client.sensors = {
            key: Sensor(
                value=sensor_data["value"],
                type=sensor_data["type"],
                device_identifier=sensor_data["device_identifier"],
            )
            for key, sensor_data in fixture_data["sensors"].items()
        }

        # Convert device metadata from JSON to DeviceMetadata objects
        client.device_metadata = {
            key: DeviceMetadata(
                name=metadata["name"],
                model=metadata["model"],
            )
            for key, metadata in fixture_data["device_metadata"].items()
        }

        # Set schedule data directly from fixture
        client.current_schedule = fixture_data["current_schedule"]

        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Homevolt integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.homevolt.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
