"""Test the Advantage Air Initialization."""
from advantage_air import ApiError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import add_mock_config, patch_get


@pytest.fixture
def mock_get():
    """Fixture to patch the Advantage Air async_get method."""
    with patch_get() as mock_get:
        yield mock_get


async def test_async_setup_entry(hass: HomeAssistant, mock_get) -> None:
    """Test a successful setup entry and unload."""

    entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_failure(hass: HomeAssistant) -> None:
    """Test a unsuccessful setup entry."""

    with patch_get(side_effect=ApiError):
        entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
