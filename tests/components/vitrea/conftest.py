"""Common fixtures for the vitrea tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vitreaclient import VitreaResponse
from vitreaclient.constants import DeviceStatus

from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Vitrea Integration",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 11502,
        },
        unique_id="vitrea_192.168.1.100_11502",
    )


@pytest.fixture
def mock_vitrea_client() -> Generator[MagicMock]:
    """Return a mocked VitreaClient."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.start_read_task = AsyncMock()

    # Store the callback for entity discovery simulation
    client._status_callback = None

    def mock_on(event_type, callback):
        """Mock the on method to store the callback."""

        if event_type == VitreaResponse.STATUS:  # Compare with enum value
            client._status_callback = callback
        return MagicMock()  # Return a mock unsubscribe function

    def mock_off(event_type, callback):
        """Mock the off method."""

        if event_type == VitreaResponse.STATUS:
            client._status_callback = None

    async def mock_status_request():
        """Mock status request that triggers entity discovery."""
        if client._status_callback:
            # Simulate discovering a cover entity
            mock_event = MagicMock()
            mock_event.node = "01"
            mock_event.key = "01"
            mock_event.status = DeviceStatus.BLIND
            mock_event.data = "050"  # 50% position
            client._status_callback(mock_event)

    client.on = mock_on
    client.off = mock_off
    # Use AsyncMock but set side_effect to call our custom mock function
    client.status_request = AsyncMock(side_effect=mock_status_request)
    client.blind_open = AsyncMock()
    client.blind_close = AsyncMock()
    client.blind_stop = AsyncMock()
    client.blind_percent = AsyncMock()

    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> MockConfigEntry:
    """Set up the vitrea integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vitrea.VitreaClient", return_value=mock_vitrea_client
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Wait again to ensure entity discovery callbacks are processed
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_cover_event():
    """Return a mock cover status event."""
    event = MagicMock()
    event.node = "01"
    event.key = "01"
    event.status = DeviceStatus.BLIND
    event.data = "050"  # 50% position
    return event
