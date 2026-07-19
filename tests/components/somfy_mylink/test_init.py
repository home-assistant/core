"""Test the Somfy MyLink setup."""

from unittest.mock import MagicMock

from pysomfymylink import (
    SomfyMyLinkApiError,
    SomfyMyLinkAuthError,
    SomfyMyLinkConnectionError,
)

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


async def test_setup_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test an auth error aborts setup and starts a reauth flow."""
    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkAuthError(
        "Invalid auth", code=-32652
    )
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_setup_retries_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test a non-auth API error retries setup instead of forcing reauth."""
    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkApiError(
        "Method not found", code=-32601
    )
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_setup_empty_result_loads_without_covers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test a reachable hub reporting no covers still loads the entry."""
    mock_somfy_mylink.status_info.return_value = []
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("cover")


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
