"""Tests for the Netio integration setup."""

from unittest.mock import MagicMock

from Netio.exceptions import AuthError, CommunicationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.netio.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_netio")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_netio")
async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "24A42C39F87E")})
    assert device == snapshot


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        pytest.param(
            CommunicationError("failed"),
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
        pytest.param(
            AuthError("invalid"), ConfigEntryState.SETUP_ERROR, id="auth_error"
        ),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_netio: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry setup errors."""
    mock_netio.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state
