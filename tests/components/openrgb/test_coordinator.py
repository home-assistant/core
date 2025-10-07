"""Tests for the OpenRGB coordinator."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from openrgb.utils import OpenRGBDisconnected

from homeassistant.components.openrgb.const import SCAN_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_reconnection_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator reconnects when update fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate the first update call failing, then second succeeding
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call succeeds after reconnect
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify that disconnect and connect were called (reconnection happened)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was called twice (once failed, once after reconnect)
    assert mock_openrgb_client.update.call_count == 2

    # Verify that the light is still available after successful reconnect
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON


async def test_reconnection_fails_second_attempt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator fails when reconnection also fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate the first update call failing, and reconnection also failing
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call would succeed if reconnect worked
    ]

    # Simulate connect raising an exception to mimic failed reconnection
    mock_openrgb_client.connect.side_effect = ConnectionRefusedError()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify that the light became unavailable after failed reconnection
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Verify that disconnect and connect were called (reconnection was attempted)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was only called in the first attempt
    mock_openrgb_client.update.assert_called_once()


async def test_normal_update_without_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that normal updates work without triggering reconnection."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate successful update
    mock_openrgb_client.update.side_effect = None
    mock_openrgb_client.update.return_value = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify that disconnect and connect were NOT called (no reconnection needed)
    mock_openrgb_client.disconnect.assert_not_called()
    mock_openrgb_client.connect.assert_not_called()

    # Verify that update was called only once
    mock_openrgb_client.update.assert_called_once()

    # Verify that the light is still available
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
