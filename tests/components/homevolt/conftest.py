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

DEVICE_IDENTIFIER = "ems_40580137858664"


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

        client.unique_id = "40580137858664"

        # Load sensor data from fixture and convert to Sensor objects
        sensors_data = json.loads(load_fixture("sensors.json", DOMAIN))
        client.sensors = {
            key: Sensor(
                value=value,
                type=key,
                device_identifier=DEVICE_IDENTIFIER,
            )
            for key, value in sensors_data.items()
        }

        # Load device metadata from fixture and convert to DeviceMetadata objects
        metadata_data = json.loads(load_fixture("device_metadata.json", DOMAIN))
        client.device_metadata = {
            key: DeviceMetadata(
                name=metadata["name"],
                model=metadata["model"],
            )
            for key, metadata in metadata_data.items()
        }

        # Load schedule data from fixture
        client.current_schedule = json.loads(load_fixture("schedule.json", DOMAIN))

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
