"""Test the Tractive switch platform."""

from unittest.mock import AsyncMock, patch

from aiotractive.exceptions import TractiveError
from syrupy import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the switch."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)

        mock_tractive_client.send_switch_event(mock_config_entry)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_on(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch can be turned on."""
    entity_id = "switch.test_pet_tracker_led"

    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_switch_event(mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_tractive_client.send_switch_event(
        mock_config_entry,
        {"tracker_id": "device_id_123", "led_control": {"active": True}},
    )
    await hass.async_block_till_done()

    assert mock_tractive_client.tracker.return_value.set_led_active.call_count == 1
    assert (
        mock_tractive_client.tracker.return_value.set_led_active.call_args[0][0] is True
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


async def test_switch_off(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch can be turned off."""
    entity_id = "switch.test_pet_tracker_buzzer"

    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_switch_event(mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_tractive_client.send_switch_event(
        mock_config_entry,
        {"tracker_id": "device_id_123", "buzzer_control": {"active": False}},
    )
    await hass.async_block_till_done()

    assert mock_tractive_client.tracker.return_value.set_buzzer_active.call_count == 1
    assert (
        mock_tractive_client.tracker.return_value.set_buzzer_active.call_args[0][0]
        is False
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_live_tracking_switch(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the live_tracking switch."""
    entity_id = "switch.test_pet_live_tracking"

    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_switch_event(mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_tractive_client.send_switch_event(
        mock_config_entry,
        {"tracker_id": "device_id_123", "live_tracking": {"active": False}},
    )
    await hass.async_block_till_done()

    assert (
        mock_tractive_client.tracker.return_value.set_live_tracking_active.call_count
        == 1
    )
    assert (
        mock_tractive_client.tracker.return_value.set_live_tracking_active.call_args[0][
            0
        ]
        is False
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_switch_on_with_exception(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch turn on with exception."""
    entity_id = "switch.test_pet_tracker_led"

    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_switch_event(mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    mock_tractive_client.tracker.return_value.set_led_active.side_effect = TractiveError

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_switch_off_with_exception(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch turn off with exception."""
    entity_id = "switch.test_pet_tracker_buzzer"

    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_switch_event(mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    mock_tractive_client.tracker.return_value.set_buzzer_active.side_effect = (
        TractiveError
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
