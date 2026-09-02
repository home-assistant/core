"""Test the ISEO Argo BLE integration setup and teardown."""

from unittest.mock import MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: None,
) -> None:
    """Test that a config entry is set up and unloaded cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried while the lock is not advertising."""
    with patch(
        "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
        return_value=None,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_setup_reads_users_once(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test an entry with an admin identity reads the user list at setup.

    Reading it on a schedule faults the lock's firmware, so setup is the only
    place it happens on its own.
    """
    await setup_integration(hass, mock_admin_config_entry)

    assert mock_admin_config_entry.state is ConfigEntryState.LOADED
    mock_iseo_client.read_users.assert_called_once()
    assert mock_admin_config_entry.runtime_data.user_coordinator.update_interval is None


@pytest.mark.parametrize(
    "error",
    [IseoAuthError("rejected"), IseoConnectionError("no link"), TimeoutError],
)
@pytest.mark.usefixtures("mock_derive_private_key")
async def test_setup_retries_when_user_read_fails(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
    error: Exception,
) -> None:
    """Test setup is retried when the lock will not hand over its user list."""
    mock_iseo_client.read_users.side_effect = error

    await setup_integration(hass, mock_admin_config_entry)

    assert mock_admin_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_setup_retries_when_device_gone_before_user_read(
    hass: HomeAssistant,
    mock_admin_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test setup is retried when the lock stops advertising mid-setup."""
    with patch(
        "homeassistant.components.iseo_argo_ble.coordinator.async_ble_device_from_address",
        return_value=None,
    ):
        await setup_integration(hass, mock_admin_config_entry)

    assert mock_admin_config_entry.state is ConfigEntryState.SETUP_RETRY
