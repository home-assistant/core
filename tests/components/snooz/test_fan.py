"""Test Snooz fan entity."""
from __future__ import annotations

from pysnooz.api import SnoozDeviceState
import pytest

from homeassistant.components import fan
from homeassistant.components.snooz.const import DOMAIN
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import SnoozFixture


async def test_turn_on(hass: HomeAssistant, snooz_fan_entity_id: str):
    """Test turning on the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_ON
    assert ATTR_ASSUMED_STATE not in state.attributes


@pytest.mark.parametrize("percentage", [1, 22, 50, 99, 100])
async def test_turn_on_with_percentage(
    hass: HomeAssistant, snooz_fan_entity_id: str, percentage: int
):
    """Test turning on the device with a percentage."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id], fan.ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_off(hass: HomeAssistant, snooz_fan_entity_id: str):
    """Test turning off the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_OFF
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_push_events(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture, snooz_fan_entity_id: str
):
    """Test state update events from snooz device."""
    mock_connected_snooz.client.trigger_state(SnoozDeviceState(False, 64))

    state = hass.states.get(snooz_fan_entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 64

    mock_connected_snooz.client.trigger_state(SnoozDeviceState(True, 12))

    state = hass.states.get(snooz_fan_entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 12


@pytest.fixture(name="snooz_fan_entity_id")
async def fixture_snooz_fan_entity_id(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> str:
    """Mock a Snooz fan entity that's connected and turned off."""
    entity_id = entity_registry.async_get(hass).async_get_entity_id(
        Platform.FAN, DOMAIN, mock_connected_snooz.device.address
    )

    yield entity_id
