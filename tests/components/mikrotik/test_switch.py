"""Tests for the Mikrotik switch platform."""

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import BRIDGE1_INTERFACE, ETHER1_INTERFACE, INTERFACE_DATA, WLAN1_INTERFACE

from tests.common import MockUser, snapshot_platform


async def test_switch_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik switch entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        config_entry = await setup_mikrotik_entry(hass, interface_data=INTERFACE_DATA)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_no_matching_interfaces(hass: HomeAssistant) -> None:
    """Test no switch entities are created for unsupported interface types."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[BRIDGE1_INTERFACE])

    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == []


@pytest.mark.parametrize(
    (
        "interface",
        "entity_id",
        "initial_state",
        "service",
        "command",
        "final_state",
    ),
    [
        pytest.param(
            ETHER1_INTERFACE,
            "switch.ether1_ethernet",
            STATE_ON,
            SERVICE_TURN_OFF,
            "/interface/disable",
            STATE_OFF,
            id="turn_off",
        ),
        pytest.param(
            WLAN1_INTERFACE,
            "switch.wlan1_wlan",
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

    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[interface])

    assert (state := hass.states.get(entity_id))
    assert state.state == initial_state

    mock_api.return_value = [{**interface, "disabled": final_state == STATE_OFF}]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api.assert_any_call(command, **{".id": interface[".id"]})

    assert (state := hass.states.get(entity_id))
    assert state.state == final_state


async def test_switch_requires_admin_user(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test a non-admin user cannot change the state of an interface."""
    user_group = await hass.auth.async_get_group(GROUP_ID_USER)
    user = MockUser(groups=[user_group]).add_to_hass(hass)

    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[ETHER1_INTERFACE])

    entity_id = "switch.ether1_ethernet"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            context=Context(user_id=user.id),
        )

    assert (
        call("/interface/disable", **{".id": ETHER1_INTERFACE[".id"]})
        not in mock_api.mock_calls
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
