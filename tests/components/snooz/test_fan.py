"""Test Snooz fan entity."""
from __future__ import annotations

from pysnooz.api import SnoozDeviceState
import pytest

from homeassistant.components import fan
from homeassistant.components.snooz.fan import FanEntity
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
    assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
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
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_push_events(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture, snooz_fan: FanEntity
):
    """Test state update events from snooz device."""
    mock_connected_snooz.client.trigger_state(SnoozDeviceState(False, 64))

    state = hass.states.get(snooz_fan.entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 64

    mock_connected_snooz.client.trigger_state(SnoozDeviceState(True, 12))

    state = hass.states.get(snooz_fan.entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 12

    mock_connected_snooz.client.trigger_disconnect()

    state = hass.states.get(snooz_fan.entity_id)
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.fixture(name="snooz_fan")
async def fixture_snooz_fan_entity(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> FanEntity:
    """Mock a Snooz fan entity that's connected and turned off."""
    fan_entities = list(hass.data[fan.DOMAIN].entities)

    assert fan_entities[0]

    yield fan_entities[0]
