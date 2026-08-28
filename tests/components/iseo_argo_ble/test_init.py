"""Test the ISEO Argo BLE integration setup and teardown."""

from unittest.mock import patch

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
