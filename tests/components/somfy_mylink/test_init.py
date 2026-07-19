"""Test the Somfy MyLink setup."""

from unittest.mock import MagicMock

from pysomfymylink import SomfyMyLinkApiError, SomfyMyLinkConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_creates_covers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test a config entry sets up the reported covers."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("cover.left_shade") is not None
    assert hass.states.get("cover.right_shade") is not None


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test a connection error triggers a retry."""
    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkConnectionError(
        "unreachable"
    )
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test an API (auth) error triggers a retry."""
    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkApiError("bad id", code=4)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_empty_result(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test an empty cover list triggers a retry."""
    mock_somfy_mylink.status_info.return_value = []
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
