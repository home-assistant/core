"""Tests of the switches of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform
from tests.components.switch import common

ENTITY_SWITCH = "switch.fakespa_filter_cycle_2_enabled"


async def test_switches(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test spa switches."""
    with patch("homeassistant.components.balboa.PLATFORMS", [Platform.SWITCH]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_switch(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa filter cycle enabled switch."""
    await init_integration(hass)

    # check if the initial state is on
    state = hass.states.get(ENTITY_SWITCH)
    assert state.state == STATE_ON

    # test calling turn off
    await common.async_turn_off(hass, ENTITY_SWITCH)
    client.configure_filter_cycle.assert_called_with(2, enabled=False)

    setattr(client, "filter_cycle_2_enabled", False)
    client.emit("")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SWITCH)
    assert state.state == STATE_OFF

    # test calling turn on
    await common.async_turn_on(hass, ENTITY_SWITCH)
    client.configure_filter_cycle.assert_called_with(2, enabled=True)
