"""Tests for the TrueNAS integration setup."""

from unittest.mock import AsyncMock, MagicMock

from aiotruenas import (
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASConnectionRefusedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import SYSTEM_ID


@pytest.mark.usefixtures("mock_truenas_system")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_truenas_client.assert_called_once_with(
        "192.168.1.10", "1-abcdef", verify_ssl=False
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_truenas_client.return_value.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_truenas_client", "mock_truenas_system")
async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the TrueNAS device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SYSTEM_ID), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize(
    ("exception", "state", "reason"),
    [
        (
            TrueNASConnectionRefusedError("refused"),
            ConfigEntryState.SETUP_RETRY,
            "update_failed",
        ),
        (
            TrueNASCallError("failed", errname="EFAULT"),
            ConfigEntryState.SETUP_RETRY,
            "update_failed",
        ),
        (
            TrueNASAuthenticationError("rejected"),
            ConfigEntryState.SETUP_ERROR,
            "invalid_auth",
        ),
        (
            TrueNASCallError("denied", errname="EACCES"),
            ConfigEntryState.SETUP_ERROR,
            "permission_denied",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
    reason: str,
) -> None:
    """Test a failing first refresh and that the connection is closed."""
    mock_truenas_system.get_system_info.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == reason
    mock_truenas_client.return_value.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_truenas_system")
async def test_setup_connect_failure(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failing connection is retried."""
    mock_truenas_client.return_value.connect.side_effect = (
        TrueNASConnectionRefusedError("refused")
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
