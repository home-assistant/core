"""Tests for the Envisalink zone bypass switch.

Platform.SWITCH is intentionally left out of PLATFORMS pending a panel
compatibility fix (see switch.py's module docstring), so these tests
temporarily re-enable it to exercise the otherwise-dormant entity.
"""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.envisalink.const import (
    PLATFORMS,
    SIGNAL_ZONE_BYPASS_UPDATE,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_envisalink

SWITCH_ENTITY = "switch.front_door_bypass"


@pytest.fixture(autouse=True)
def enable_switch_platform() -> None:
    """Temporarily enable the dormant switch platform for these tests."""
    with patch(
        "homeassistant.components.envisalink.PLATFORMS",
        [*PLATFORMS, Platform.SWITCH],
    ):
        yield


async def test_switch_is_on(hass: HomeAssistant, mock_controller: MagicMock) -> None:
    """Test the switch reflects the zone's bypass status on an update.

    pyenvisalink has no callback that fires SIGNAL_ZONE_BYPASS_UPDATE yet
    (part of why this platform isn't wired into PLATFORMS), so the signal is
    dispatched directly rather than through a controller callback.
    """
    assert await setup_envisalink(hass)
    assert hass.states.get(SWITCH_ENTITY).state == STATE_OFF

    mock_controller.alarm_state["zone"][1]["bypassed"] = True
    async_dispatcher_send(hass, SIGNAL_ZONE_BYPASS_UPDATE, {1: True})
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY).state == STATE_ON


async def test_switch_turn_on(hass: HomeAssistant, mock_controller: MagicMock) -> None:
    """Test turning on the switch toggles the zone bypass."""
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": SWITCH_ENTITY},
        blocking=True,
    )

    mock_controller.toggle_zone_bypass.assert_called_once_with(1)


async def test_switch_turn_off(hass: HomeAssistant, mock_controller: MagicMock) -> None:
    """Test turning off the switch toggles the zone bypass."""
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": SWITCH_ENTITY},
        blocking=True,
    )

    mock_controller.toggle_zone_bypass.assert_called_once_with(1)


async def test_switch_update_filtering(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test bypass updates are filtered by zone; None applies to all."""
    assert await setup_envisalink(hass)
    mock_controller.alarm_state["zone"][1]["bypassed"] = True

    # An update for a different zone is ignored.
    async_dispatcher_send(hass, SIGNAL_ZONE_BYPASS_UPDATE, {2: True})
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH_ENTITY).state == STATE_OFF

    # A None bypass_map applies to every entity.
    async_dispatcher_send(hass, SIGNAL_ZONE_BYPASS_UPDATE, None)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH_ENTITY).state == STATE_ON
