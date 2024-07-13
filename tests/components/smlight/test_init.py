"Test SMLIGHT SLZB device integration initialization."

import pytest

from homeassistant.components.smlight import SmDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.usefixtures(
        "setup_platform",
        "mock_smlight_client",
    )
]


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert isinstance(mock_config_entry.runtime_data, SmDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.invalid_auth
async def test_async_setup_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry when authentication fails."""
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
