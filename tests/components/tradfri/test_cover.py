"""Tradfri cover (recognised as blinds in the IKEA ecosystem) platform tests."""

import json
from typing import Any

import pytest
from pytradfri.const import ATTR_ID, ATTR_REACHABLE_STATE, ATTR_START_BLINDS
from pytradfri.device import Device

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .common import CommandStore, setup_integration


@pytest.fixture(scope="module")
def blind_without_values(blind: str) -> str:
    """Return a blind response whose control reports no values."""
    response = json.loads(blind)
    response[ATTR_START_BLINDS] = [{ATTR_ID: 0}]
    return json.dumps(response)


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
    assert state.state == CoverState.OPEN
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
        ("set_cover_position", {"position": 100}, CoverState.OPEN, 100),
        ("set_cover_position", {"position": 0}, CoverState.CLOSED, 0),
        ("open_cover", {}, CoverState.OPEN, 100),
        ("close_cover", {}, CoverState.CLOSED, 0),
        ("stop_cover", {}, CoverState.OPEN, 60),
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
    assert state.state == CoverState.OPEN
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


@pytest.mark.parametrize("device", ["blind_without_values"], indirect=True)
async def test_cover_without_values(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test a cover whose control reports no values can still be positioned."""
    entity_id = "cover.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15

    await hass.services.async_call(
        COVER_DOMAIN,
        "set_cover_position",
        {"entity_id": entity_id, "position": 30},
        blocking=True,
    )

    await command_store.trigger_observe_callback(hass, device)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 30
