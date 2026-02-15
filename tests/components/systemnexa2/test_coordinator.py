"""Test the System Nexa 2 coordinator."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from sn2 import (
    ConnectionStatus,
    OnOffSetting,
    SettingsUpdate,
    StateChange,
)
from sn2.device import UpdateEvent

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def find_update_callback(
    mock: MagicMock,
) -> Callable[[UpdateEvent], Awaitable[None]]:
    """Find the update callback that was registered with the device."""
    for call in mock.initiate_device.call_args_list:
        if call.kwargs.get("on_update"):
            return call.kwargs["on_update"]
    pytest.fail("Update callback not found in mock calls")


async def test_coordinator_connection_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles connection status updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Initially, the relay switch should be off (state=1.0 from fixture)
    state = hass.states.get("switch.test_device_relay_1")
    assert state is not None
    assert state.state == STATE_ON

    # Simulate device disconnection
    await update_callback(ConnectionStatus(connected=False))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_UNAVAILABLE

    # Simulate reconnection and state update
    await update_callback(ConnectionStatus(connected=True))
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_ON


async def test_coordinator_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles state change updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Change state to off (0.0)
    await update_callback(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state is not None
    assert state.state == STATE_OFF

    # Change state to on (1.0)
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_ON


async def test_coordinator_settings_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles settings updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Get initial state of 433Mhz switch (should be on from fixture)
    state = hass.states.get("switch.test_device_433_mhz")
    assert state is not None
    assert state.state == STATE_ON

    # Get the settings from the device mock and change 433Mhz to disabled
    device = mock_system_nexa_2_device.return_value
    device.settings[0].is_enabled.return_value = False  # 433Mhz

    # Simulate settings update where 433Mhz is now disabled
    await update_callback(SettingsUpdate(settings=device.settings))
    # Need state update to trigger coordinator data update
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_433_mhz")
    assert state.state == STATE_OFF
