"""Tradfri switch (recognised as sockets in the IKEA ecosystem) platform tests."""

from __future__ import annotations

import pytest
from pytradfri.const import ATTR_REACHABLE_STATE
from pytradfri.device import Device

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import CommandStore, setup_integration

from tests.common import load_fixture


@pytest.fixture(scope="module")
def outlet() -> str:
    """Return an outlet response."""
    return load_fixture("outlet.json", DOMAIN)


@pytest.mark.parametrize("device", ["outlet"], indirect=True)
async def test_switch_available(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test switch available property."""
    entity_id = "switch.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device", ["outlet"], indirect=True)
@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        ("turn_on", STATE_ON),
        ("turn_off", STATE_OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
    service: str,
    expected_state: str,
) -> None:
    """Test turning switch on/off."""
    entity_id = "switch.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    await command_store.trigger_observe_callback(hass, device)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
