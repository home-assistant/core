"""Common fixtures for the vitrea tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
            CONF_HOST: "192.168.1.136",
            CONF_PORT: 11502,
        },
        unique_id="vitrea_192.168.1.136_11502",
    )


@pytest.fixture
def mock_vitrea_client() -> Generator[MagicMock]:
    """Return a mocked VitreaClient."""
    with patch("homeassistant.components.vitrea.VitreaClient") as client_mock:
        client = client_mock.return_value
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.start_read_task = AsyncMock()
        client.status_request = AsyncMock()
        client.on = MagicMock()
        client.off = MagicMock()
        client.blind_open = AsyncMock()
        client.blind_close = AsyncMock()
        client.blind_stop = AsyncMock()
        client.blind_percent = AsyncMock()
        yield client


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
