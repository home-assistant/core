"""Test setup retries and listener lifetime."""

from unittest.mock import AsyncMock, patch

from aioelecway import ElecwayError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_client")


async def test_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Unloading cancels the stream and closes its socket."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.client is mock_client
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.disconnect.assert_awaited_once()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ElecwayError("Offline"), id="offline"),
        pytest.param(RuntimeError("Unexpected"), id="unexpected"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    error: Exception,
) -> None:
    """Initial failures close the connection and retry without starting a listener."""
    mock_client.connect.side_effect = error
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.disconnect.assert_awaited_once()
    mock_client.updates.assert_not_called()


async def test_platform_setup_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """A failure after the initial report must still close the connection."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError("Platform failed"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.disconnect.assert_awaited_once()
    mock_client.updates.assert_not_called()
