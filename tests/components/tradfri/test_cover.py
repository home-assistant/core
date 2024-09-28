"""Tradfri cover (recognised as blinds in the IKEA ecosystem) platform tests."""

from __future__ import annotations

from typing import Any

import pytest
from pytradfri.const import ATTR_REACHABLE_STATE
from pytradfri.device import Device

from homeassistant.components.cover import ATTR_CURRENT_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import CommandStore, setup_integration


@pytest.mark.parametrize("device", ["blind"], indirect=True)
async def test_cover_available(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test cover available property."""
    entity_id = "cover.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 60
    assert state.attributes["model"] == "FYRTUR block-out roller blind"

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device", ["blind"], indirect=True)
@pytest.mark.parametrize(
    ("service", "service_data", "expected_state", "expected_position"),
    [
        ("set_cover_position", {"position": 100}, STATE_OPEN, 100),
        ("set_cover_position", {"position": 0}, STATE_CLOSED, 0),
        ("open_cover", {}, STATE_OPEN, 100),
        ("close_cover", {}, STATE_CLOSED, 0),
        ("stop_cover", {}, STATE_OPEN, 60),
    ],
)
async def test_cover_services(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
    service: str,
    service_data: dict[str, Any],
    expected_state: str,
    expected_position: int,
) -> None:
    """Test cover services."""
    entity_id = "cover.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 60

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {"entity_id": entity_id, **service_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    await command_store.trigger_observe_callback(hass, device)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position
