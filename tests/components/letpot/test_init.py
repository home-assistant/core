"""Test the LetPot integration initialization and setup."""

from unittest.mock import MagicMock

from letpot.exceptions import (
    LetPotAuthenticationException,
    LetPotConnectionException,
    LetPotException,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2025-01-31 00:00:00")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
) -> None:
    """Test config entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.refresh_token.assert_not_called()  # Didn't refresh valid token
    mock_client.get_devices.assert_called_once()
    mock_device_client.subscribe.assert_called_once()
    mock_device_client.get_current_status.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_device_client.disconnect.assert_called_once()


@pytest.mark.freeze_time("2025-02-15 00:00:00")
async def test_refresh_authentication_on_load(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
) -> None:
    """Test expired access token refreshed when needed to load config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.refresh_token.assert_called_once()

    # Check loading continued as expected after refreshing token
    mock_client.get_devices.assert_called_once()
    mock_device_client.subscribe.assert_called_once()
    mock_device_client.get_current_status.assert_called_once()


@pytest.mark.freeze_time("2025-03-01 00:00:00")
async def test_refresh_token_error_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test expired refresh token aborting config entry loading."""
    mock_client.refresh_token.side_effect = LetPotAuthenticationException

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.refresh_token.assert_called_once()
    mock_client.get_devices.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "config_entry_state"),
    [
        (LetPotAuthenticationException, ConfigEntryState.SETUP_ERROR),
        (LetPotConnectionException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_get_devices_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    exception: Exception,
    config_entry_state: ConfigEntryState,
) -> None:
    """Test config entry errors if an exception is raised when getting devices."""
    mock_client.get_devices.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is config_entry_state
    mock_client.get_devices.assert_called_once()
    mock_device_client.subscribe.assert_not_called()


async def test_device_subscribe_authentication_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
) -> None:
    """Test config entry errors if it is not allowed to subscribe to device updates."""
    mock_device_client.subscribe.side_effect = LetPotAuthenticationException

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_device_client.subscribe.assert_called_once()
    mock_device_client.get_current_status.assert_not_called()


async def test_device_refresh_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
) -> None:
    """Test config entry errors with retry if getting a device state update fails."""
    mock_device_client.get_current_status.side_effect = LetPotException

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device_client.get_current_status.assert_called_once()
