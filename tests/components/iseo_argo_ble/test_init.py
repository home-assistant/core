"""Test the ISEO Argo BLE integration setup and teardown."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
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
async def test_setup_succeeds_before_the_lock_is_seen(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup does not wait for the lock to be cached.

    After a restart no scanner has seen the lock until it next advertises, so
    refusing to set up would leave it without an entity for minutes.
    """
    with patch(
        "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
        return_value=None,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("lock.iseo_lock").state == STATE_UNKNOWN
