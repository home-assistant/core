"""Test Snooz fan entity."""
from __future__ import annotations

from pysnooz.api import SnoozDeviceState
from pysnooz.commands import SnoozCommandData
import pytest

from homeassistant.components import fan
from homeassistant.components.snooz import DOMAIN
from homeassistant.components.snooz.fan import (
    ATTR_LAST_COMMAND_SUCCESSFUL,
    ATTR_TRANSITION,
    ATTR_VOLUME,
    SERVICE_DISCONNECT,
    FanEntity,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import SnoozFixture


async def test_turn_on(hass: HomeAssistant, snooz_fan: FanEntity):
    """Test turning on the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert ATTR_ASSUMED_STATE not in state.attributes


@pytest.mark.parametrize("percentage", [1, 22, 50, 99, 100])
async def test_turn_on_with_percentage(
    hass: HomeAssistant, snooz_fan: FanEntity, percentage: int
):
    """Test turning on the device with a percentage."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id], fan.ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_on_with_transition(hass: HomeAssistant, snooz_fan: FanEntity):
    """Test turning on the device with a transition."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id], ATTR_TRANSITION: 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_on_with_transition_and_volume(
    hass: HomeAssistant, snooz_fan: FanEntity
):
    """Test turning on the device with a transition and target volume."""
    # increases volume
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id], ATTR_TRANSITION: 1, ATTR_VOLUME: 33},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33
    assert ATTR_ASSUMED_STATE not in state.attributes

    # decreases volume
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id], ATTR_TRANSITION: 1, ATTR_VOLUME: 12},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert state.attributes[fan.ATTR_PERCENTAGE] == 12
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_off(hass: HomeAssistant, snooz_fan: FanEntity):
    """Test turning off the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_off_with_transition(hass: HomeAssistant, snooz_fan: FanEntity):
    """Test turning off the device with a transition."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id], ATTR_TRANSITION: 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LAST_COMMAND_SUCCESSFUL] is True
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_service_disconnect(hass: HomeAssistant, snooz_fan: FanEntity):
    """Test service to disconnect device."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan.entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DISCONNECT,
        {ATTR_ENTITY_ID: [snooz_fan.entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan.entity_id)
    assert state.attributes[ATTR_ASSUMED_STATE] is True


async def test_push_events(
    hass: HomeAssistant, mock_snooz: SnoozFixture, snooz_fan: FanEntity
):
    """Test state update events from snooz device."""
    mock_snooz.client.trigger_state(SnoozDeviceState(False, 64))

    state = hass.states.get(snooz_fan.entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 64

    mock_snooz.client.trigger_state(SnoozDeviceState(True, 12))

    state = hass.states.get(snooz_fan.entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 12

    mock_snooz.client.trigger_disconnect()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.fixture(name="snooz_fan")
async def fixture_snooz_fan_entity(
    hass: HomeAssistant, mock_snooz: SnoozFixture
) -> FanEntity:
    """Mock a Snooz fan entity that's connected and turned off."""
    await mock_snooz.data.device.async_execute_command(
        SnoozCommandData(on=False, volume=0)
    )

    fan_entities = list(hass.data[fan.DOMAIN].entities)

    assert fan_entities[0]

    yield fan_entities[0]
