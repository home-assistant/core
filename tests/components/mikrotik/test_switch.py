"""Tests for the Mikrotik switch platform."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import BRIDGE1_INTERFACE, ETHER1_INTERFACE, INTERFACE_DATA, WLAN1_INTERFACE

from tests.common import snapshot_platform

WIFI1_INTERFACE = {
    ".id": "*4",
    "name": "wifi1",
    "type": "wifi",
    "mac-address": "02:00:00:00:00:04",
    "running": True,
    "disabled": False,
}
WIFI2_INTERFACE = {
    ".id": "*5",
    "name": "wifi2",
    "type": "wifi",
    "mac-address": "02:00:00:00:00:05",
    "running": False,
    "disabled": True,
}


async def test_switch_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik switch entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        config_entry = await setup_mikrotik_entry(
            hass, interface_data=[*INTERFACE_DATA, WIFI1_INTERFACE, WIFI2_INTERFACE]
        )

    assert sorted(hass.states.async_entity_ids(SWITCH_DOMAIN)) == [
        "switch.ether1_ethernet",
        "switch.wifi1_wlan",
        "switch.wifi2_wlan",
        "switch.wlan1_wlan",
    ]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("interface_type", ["bridge", "vlan", "wireguard", None])
async def test_switch_no_matching_interfaces(
    hass: HomeAssistant, interface_type: str | None
) -> None:
    """Test no switch entities are created for unsupported interface types."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(
            hass, interface_data=[{**BRIDGE1_INTERFACE, "type": interface_type}]
        )

    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == []


@pytest.mark.parametrize(
    ("interface", "entity_id"),
    [
        pytest.param(ETHER1_INTERFACE, "switch.ether1_ethernet", id="ether"),
        pytest.param(WLAN1_INTERFACE, "switch.wlan1_wlan", id="wlan"),
        pytest.param(WIFI1_INTERFACE, "switch.wifi1_wlan", id="wifi1"),
        pytest.param(WIFI2_INTERFACE, "switch.wifi2_wlan", id="wifi2"),
    ],
)
@pytest.mark.parametrize(
    (
        "initial_state",
        "service",
        "command",
        "final_state",
    ),
    [
        pytest.param(
            STATE_ON,
            SERVICE_TURN_OFF,
            "/interface/disable",
            STATE_OFF,
            id="turn_off",
        ),
        pytest.param(
            STATE_OFF,
            SERVICE_TURN_ON,
            "/interface/enable",
            STATE_ON,
            id="turn_on",
        ),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_api: MagicMock,
    interface: dict[str, Any],
    entity_id: str,
    initial_state: str,
    service: str,
    command: str,
    final_state: str,
) -> None:
    """Test turning a Mikrotik switch on/off updates state via the coordinator."""

    interfaces = {
        item[".id"]: {**item, "disabled": initial_state == STATE_OFF}
        for item in (
            ETHER1_INTERFACE,
            WLAN1_INTERFACE,
            WIFI1_INTERFACE,
            WIFI2_INTERFACE,
        )
    }
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=list(interfaces.values()))

    assert (state := hass.states.get(entity_id))
    assert state.state == initial_state

    interfaces[interface[".id"]]["disabled"] = final_state == STATE_OFF
    mock_api.return_value = list(interfaces.values())

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api.assert_any_call(command, **{".id": interface[".id"]})

    assert (state := hass.states.get(entity_id))
    assert state.state == final_state
