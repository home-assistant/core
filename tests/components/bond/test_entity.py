"""Tests for the Bond entities."""
import asyncio
from datetime import timedelta
from unittest.mock import patch

from bond_api import BPUPSubscriptions, DeviceType

from homeassistant import core
from homeassistant.components import fan
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import CoreState
from homeassistant.util import utcnow

from .common import patch_bond_device_state, setup_platform

from tests.common import async_fire_time_changed


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": ["SetSpeed", "SetDirection"],
    }


async def test_bpup_goes_offline_and_recovers_same_entity(hass: core.HomeAssistant):
    """Test that push updates fail and we fallback to polling and then bpup recovers.

    The BPUP recovery is triggered by an update for the entity and
    we do not fallback to polling because state is in sync.
    """
    bpup_subs = BPUPSubscriptions()
    with patch(
        "homeassistant.components.bond.BPUPSubscriptions",
        return_value=bpup_subs,
    ):
        await setup_platform(
            hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
        )

    bpup_subs.notify(
        {
            "s": 200,
            "t": "bond/test-device-id/update",
            "b": {"power": 1, "speed": 3, "direction": 0},
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.name_1").attributes[fan.ATTR_PERCENTAGE] == 100

    bpup_subs.notify(
        {
            "s": 200,
            "t": "bond/test-device-id/update",
            "b": {"power": 1, "speed": 1, "direction": 0},
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.name_1").attributes[fan.ATTR_PERCENTAGE] == 33

    bpup_subs.last_message_time = 0
    with patch_bond_device_state(side_effect=asyncio.TimeoutError):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE

    # Ensure we do not poll to get the state
    # since bpup has recovered and we know we
    # are back in sync
    with patch_bond_device_state(side_effect=Exception):
        bpup_subs.notify(
            {
                "s": 200,
                "t": "bond/test-device-id/update",
                "b": {"power": 1, "speed": 2, "direction": 0},
            }
        )
        await hass.async_block_till_done()

    state = hass.states.get("fan.name_1")
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66


async def test_bpup_goes_offline_and_recovers_different_entity(
    hass: core.HomeAssistant,
):
    """Test that push updates fail and we fallback to polling and then bpup recovers.

    The BPUP recovery is triggered by an update for a different entity which
    forces a poll since we need to re-get the state.
    """
    bpup_subs = BPUPSubscriptions()
    with patch(
        "homeassistant.components.bond.BPUPSubscriptions",
        return_value=bpup_subs,
    ):
        await setup_platform(
            hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
        )

    bpup_subs.notify(
        {
            "s": 200,
            "t": "bond/test-device-id/update",
            "b": {"power": 1, "speed": 3, "direction": 0},
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.name_1").attributes[fan.ATTR_PERCENTAGE] == 100

    bpup_subs.notify(
        {
            "s": 200,
            "t": "bond/test-device-id/update",
            "b": {"power": 1, "speed": 1, "direction": 0},
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.name_1").attributes[fan.ATTR_PERCENTAGE] == 33

    bpup_subs.last_message_time = 0
    with patch_bond_device_state(side_effect=asyncio.TimeoutError):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE

    bpup_subs.notify(
        {
            "s": 200,
            "t": "bond/not-this-device-id/update",
            "b": {"power": 1, "speed": 2, "direction": 0},
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE

    with patch_bond_device_state(return_value={"power": 1, "speed": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=430))
        await hass.async_block_till_done()

    state = hass.states.get("fan.name_1")
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33


async def test_polling_fails_and_recovers(hass: core.HomeAssistant):
    """Test that polling fails and we recover."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_device_state(side_effect=asyncio.TimeoutError):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE

    with patch_bond_device_state(return_value={"power": 1, "speed": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    state = hass.states.get("fan.name_1")
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33


async def test_polling_stops_at_the_stop_event(hass: core.HomeAssistant):
    """Test that polling stops at the stop event."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_device_state(side_effect=asyncio.TimeoutError):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    hass.state = CoreState.stopping
    await hass.async_block_till_done()

    with patch_bond_device_state(return_value={"power": 1, "speed": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=230))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == STATE_UNAVAILABLE
