"""Test the FMD init setup/unload."""

from unittest.mock import MagicMock, patch

from fmd_api import AuthenticationError, FmdApiException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("device_tracker.fmd_test_user") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_fmd_client.close.assert_awaited_once()


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test ConfigEntryAuthFailed when artifacts are rejected."""
    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
        side_effect=AuthenticationError("nope"),
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test ConfigEntryNotReady when the server is unreachable."""
    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
        side_effect=FmdApiException("boom"),
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_refresh_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fmd_client: MagicMock,
) -> None:
    """Test setup retries when the initial location fetch fails."""
    mock_fmd_client.get_locations.side_effect = FmdApiException("server down")

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
