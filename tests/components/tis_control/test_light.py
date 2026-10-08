"""Test the TIS Control lights."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tis_smartbus import OpCode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tis_control.const import POLL_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CHANNEL_1 = "light.living_dimmer_channel_1"
CHANNEL_2 = "light.living_dimmer_channel_2"


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    setup_entry: MockConfigEntry,
) -> None:
    """Test the light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


@pytest.mark.usefixtures("setup_entry")
async def test_turn_on_off(hass: HomeAssistant, mock_gateway: MagicMock) -> None:
    """Test switching and dimming a channel."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: CHANNEL_2, ATTR_BRIGHTNESS: 128, ATTR_TRANSITION: 2},
        blocking=True,
    )
    mock_gateway.set_channel.assert_called_with(1, 5, 2, 50, 2)
    assert hass.states.get(CHANNEL_2).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: CHANNEL_2}, blocking=True
    )
    mock_gateway.set_channel.assert_called_with(1, 5, 2, 0, 0)
    assert hass.states.get(CHANNEL_2).state == STATE_OFF

    # Turning on without a brightness restores the last level.
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CHANNEL_2}, blocking=True
    )
    mock_gateway.set_channel.assert_called_with(1, 5, 2, 50, 0)


@pytest.mark.usefixtures("setup_entry")
async def test_turn_on_keeps_current_level(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Turning on a channel that is already on keeps its level."""
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CHANNEL_1}, blocking=True
    )
    mock_gateway.set_channel.assert_called_with(1, 5, 1, 100, 0)


@pytest.mark.usefixtures("setup_entry")
async def test_state_pushed_from_the_bus(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """A wall switch changes channel 1: the module announces [channel, 0xF8, level]."""
    assert hass.states.get(CHANNEL_1).state == STATE_ON
    mock_gateway.push((1, 5), OpCode.SINGLE_CHANNEL_REPLY, bytes.fromhex("01f800"))
    await hass.async_block_till_done()
    assert hass.states.get(CHANNEL_1).state == STATE_OFF

    # Telegrams from other modules, or without a level, are ignored.
    mock_gateway.push((2, 9), OpCode.SINGLE_CHANNEL_REPLY, bytes.fromhex("01f864"))
    mock_gateway.push((1, 5), OpCode.REMARK_REPLY, b"Living Dimmer")
    await hass.async_block_till_done()
    assert hass.states.get(CHANNEL_1).state == STATE_OFF


async def test_unavailable_and_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_gateway: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A module that stops answering becomes unavailable, and recovers."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CHANNEL_1).state == STATE_ON

    levels = mock_gateway.levels.pop((1, 5))
    for _ in range(2):
        freezer.tick(POLL_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(CHANNEL_1).state == STATE_UNAVAILABLE

    mock_gateway.levels[(1, 5)] = levels
    freezer.tick(POLL_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CHANNEL_1).state == STATE_ON
