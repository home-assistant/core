"""Common fixtures for the vitrea tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vitreaclient.constants import DeviceStatus, VitreaResponse

from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vitrea.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Vitrea Integration",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.136",
            CONF_PORT: 11502,
        },
        unique_id="vitrea_192.168.1.136_11502",
    )


@pytest.fixture
def mock_vitrea_client() -> Generator[MagicMock]:
    """Return a mocked VitreaClient from the vitreaclient PyPI package."""
    with (
        patch("homeassistant.components.vitrea.VitreaClient") as client_mock,
        patch("vitreaclient.client.VitreaClient") as vitrea_client_mock,
    ):
        # Mock the client instance
        client = client_mock.return_value
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.get_status = AsyncMock()
        client.send_command = AsyncMock()
        client.set_timer = AsyncMock()
        client.start_read_task = AsyncMock()
        client.status_request = AsyncMock()
        client.on = MagicMock()
        client.off = MagicMock()
        client.write = AsyncMock()
        client._cleanup_connection = AsyncMock()  # Add this async mock

        # Also mock the vitreaclient version
        vitrea_client_mock.return_value = client

        yield client


@pytest.fixture
def mock_vitrea_response() -> MagicMock:
    """Return a mocked VitreaResponse from the vitreaclient PyPI package."""
    return MagicMock(spec=VitreaResponse)


@pytest.fixture
def mock_device_status() -> MagicMock:
    """Return a mocked DeviceStatus from the vitreaclient PyPI package."""
    return MagicMock(spec=DeviceStatus)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> MockConfigEntry:
    """Set up the vitrea integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Pre-populate runtime_data with test entities to avoid discovery timeout
    mock_config_entry.runtime_data = {"switches": [], "covers": [], "timers": []}

    with (
        patch(
            "homeassistant.components.vitrea.VitreaClient",
            return_value=mock_vitrea_client,
        ),
        patch("vitreaclient.client.VitreaClient", return_value=mock_vitrea_client),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


# Sample device data for testing
SAMPLE_SWITCH_DATA = [
    ["01", "01", "O", ""],  # Regular switch, on
    ["01", "02", "F", ""],  # Regular switch, off
    ["02", "01", "O", "120"],  # Timer switch, on with 120 minutes
    ["02", "02", "F", "000"],  # Timer switch, off
]

SAMPLE_COVER_DATA = [
    ["03", "01", "050"],  # Cover at 50% position
    ["03", "02", "100"],  # Cover fully open
    ["03", "03", "000"],  # Cover fully closed
]
