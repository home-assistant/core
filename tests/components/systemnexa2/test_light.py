"""Test the System Nexa 2 light platform."""

from unittest.mock import MagicMock, patch

import pytest
from sn2 import ConnectionStatus, StateChange
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import find_update_callback

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_light_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test the light entities."""
    mock_config_entry.add_to_hass(hass)

    # Only load the light platform for snapshot testing
    with patch(
        "homeassistant.components.systemnexa2.PLATFORMS",
        [Platform.LIGHT],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_light_only_for_dimmable_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test that light entity is only created for dimmable devices."""
    # The mock_system_nexa_2_device has dimmable=False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Light entity should NOT exist for non-dimmable device
    state = hass.states.get("light.outdoor_smart_plug")
    assert state is None


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_light_control_operations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test all light control operations (on/off/toggle/dim)."""
    device = mock_system_nexa_2_device.return_value
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "light.in_wall_dimmer_light"

    # Verify initial state (should be on with 50% brightness from fixture)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Test turn on without brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.turn_on.assert_called_once()
    device.set_brightness.assert_not_called()
    device.turn_on.reset_mock()

    # Test turn on with brightness=128 (50% in HA scale 0-255)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    device.set_brightness.assert_called_once_with(128 / 255)
    device.turn_on.assert_not_called()
    device.set_brightness.reset_mock()

    # Test turn on with brightness=255 (100% in HA scale)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    device.set_brightness.assert_called_once_with(255 / 255)
    device.set_brightness.reset_mock()

    # Test turn on with brightness=1 (minimum non-zero in HA scale)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 1},
        blocking=True,
    )
    device.set_brightness.assert_called_once_with(1 / 255)
    device.set_brightness.reset_mock()

    # Test turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.turn_off.assert_called_once()
    device.turn_off.reset_mock()

    # No reason to test toggle service as its an internal function using turn_on/off


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_light_brightness_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test light brightness property conversion."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Test with state = 0.5 (50% in device scale, should be 128 in HA scale)
    await update_callback(StateChange(state=0.5))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128

    # Test with state = 1.0 (100% in device scale, should be 255 in HA scale)
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255

    # Test with state = 0.0 (0% - light should be off)
    await update_callback(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_OFF

    # Test with state = 0.1 (10% in device scale, should be 26 in HA scale)
    await update_callback(StateChange(state=0.1))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 26


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_light_is_on_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test light is_on property."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Test with state > 0 (light is on)
    await update_callback(StateChange(state=0.5))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON

    # Test with state = 0 (light is off)
    await update_callback(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_coordinator_connection_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles connection status updates for light."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Initially, the light should be on (state=0.5 from fixture)
    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON

    # Simulate device disconnection
    await update_callback(ConnectionStatus(connected=False))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate reconnection and state update
    await update_callback(ConnectionStatus(connected=True))
    await update_callback(StateChange(state=0.75))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 191  # 0.75 * 255 ≈ 191


@pytest.mark.parametrize("dimmable", [True], indirect=True)
async def test_coordinator_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles state change updates for light."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Change state to off (0.0)
    await update_callback(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_OFF

    # Change state to 25% (0.25)
    await update_callback(StateChange(state=0.25))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 64  # 0.25 * 255 ≈ 64

    # Change state to full brightness (1.0)
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("light.in_wall_dimmer_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255
