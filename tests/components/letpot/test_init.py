"""Test the LetPot integration initialization and setup."""

from unittest.mock import MagicMock

from letpot.exceptions import LetPotAuthenticationException, LetPotConnectionException
import pytest

from homeassistant.components.letpot.const import DOMAIN
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
    assert len(mock_client.refresh_token.mock_calls) == 0  # Didn't refresh valid token
    assert len(mock_client.get_devices.mock_calls) == 1
    assert len(mock_device_client.subscribe.mock_calls) == 1
    assert len(mock_device_client.get_current_status.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert len(mock_device_client.disconnect.mock_calls) == 1


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
    assert len(mock_client.refresh_token.mock_calls) == 1

    # Check loading continued as expected after refreshing token
    assert len(mock_client.get_devices.mock_calls) == 1
    assert len(mock_device_client.subscribe.mock_calls) == 1
    assert len(mock_device_client.get_current_status.mock_calls) == 1


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
    assert len(mock_client.refresh_token.mock_calls) == 1
    assert len(mock_client.get_devices.mock_calls) == 0


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
    assert len(mock_client.get_devices.mock_calls) == 1
    assert len(mock_device_client.subscribe.mock_calls) == 0
