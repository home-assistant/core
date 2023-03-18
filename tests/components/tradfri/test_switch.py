"""Tradfri switch (recognised as sockets in the IKEA ecosystem) platform tests."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytradfri.const import ATTR_REACHABLE_STATE
from pytradfri.device import Device
from pytradfri.device.socket import Socket

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import setup_integration, trigger_observe_callback

from tests.common import load_fixture


@pytest.fixture(scope="module")
def outlet() -> dict[str, Any]:
    """Return an outlet response."""
    return json.loads(load_fixture("outlet.json", DOMAIN))


@pytest.fixture
def socket(outlet: dict[str, Any]) -> Socket:
    """Return socket."""
    device = Device(outlet)
    socket_control = device.socket_control
    assert socket_control
    return socket_control.sockets[0]


async def test_switch_available(
    hass: HomeAssistant,
    mock_gateway: Mock,
    mock_api_factory: MagicMock,
    socket: Socket,
) -> None:
    """Test switch available property."""
    entity_id = "switch.test"
    device = socket.device
    mock_gateway.mock_devices.append(device)
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await trigger_observe_callback(
        hass, mock_gateway, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        ("turn_on", STATE_ON),
        ("turn_off", STATE_OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_gateway: Mock,
    mock_api_factory: MagicMock,
    socket: Socket,
    service: str,
    expected_state: str,
) -> None:
    """Test turning switch on/off."""
    entity_id = "switch.test"
    device = socket.device
    mock_gateway.mock_devices.append(device)
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

    await trigger_observe_callback(hass, mock_gateway, device)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
