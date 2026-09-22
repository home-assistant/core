"""Tests for LANBON switch platform."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.lanbon.switch import LanbonSwitch
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import GATEWAY_ID, snapshot

from tests.common import MockConfigEntry


async def test_switch_entities_only_type_switch(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Only LOIP type=switch components become switch entities."""
    states = hass.states.async_all("switch")
    assert len(states) == 1
    assert states[0].state == STATE_OFF


async def test_turn_on_off(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: AsyncMock,
) -> None:
    """Test turn on and off send set_on."""
    entity_id = hass.states.async_entity_ids("switch")[0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_lanbon_client.send_command.assert_awaited()
    args = mock_lanbon_client.send_command.await_args.args
    assert args[2] == "set_on"
    assert args[3] == {"on": True}

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert mock_lanbon_client.send_command.await_args.args[3] == {"on": False}
    assert hass.states.get(entity_id).state in {STATE_ON, STATE_OFF}


@pytest.mark.parametrize("state", [{}, {"on": "false"}, {"on": 0}])
async def test_invalid_switch_state_is_unknown(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    state: dict,
) -> None:
    """Malformed on values must not be presented as a definite on/off state."""
    coordinator = setup_integration.runtime_data
    snap = snapshot()
    component = replace(snap.devices[0].components[0], state=state)
    coordinator.async_set_updated_data(
        replace(snap, devices=(replace(snap.devices[0], components=(component,)),))
    )
    assert LanbonSwitch(coordinator, GATEWAY_ID, "switch:1").is_on is None


async def test_child_metadata_and_gateway_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: MockConfigEntry,
) -> None:
    """A child uses its own metadata and the gateway registry ID."""
    coordinator = setup_integration.runtime_data
    snap = snapshot()
    child = replace(snap.devices[0], id="child-1", name="Wall Switch", model="L8-2G")
    coordinator.async_set_updated_data(replace(snap, devices=(snap.devices[0], child)))
    gateway = device_registry.async_get_device_by_identifier(
        ("lanbon", GATEWAY_ID), setup_integration.entry_id
    )
    assert gateway is not None
    info = LanbonSwitch(coordinator, "child-1", "switch:1").device_info
    assert info["name"] == "Wall Switch"
    assert info["model"] == "L8-2G"
    assert info["via_device_id"] == gateway.id


async def test_gateway_link_is_scoped_to_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: AsyncMock,
) -> None:
    """A matching identifier in another config entry is not our gateway."""
    other_entry = MockConfigEntry(domain="lanbon", unique_id="other-gateway")
    other_entry.add_to_hass(hass)
    other_gateway = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("lanbon", GATEWAY_ID)},
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    snap = snapshot()
    child = replace(snap.devices[0], id="child-1", name="Wall Switch")
    coordinator.async_set_updated_data(replace(snap, devices=(snap.devices[0], child)))
    gateway = device_registry.async_get_device_by_identifier(
        ("lanbon", GATEWAY_ID), mock_config_entry.entry_id
    )
    assert gateway is not None
    assert gateway.id != other_gateway.id
    assert (
        LanbonSwitch(coordinator, "child-1", "switch:1").device_info["via_device_id"]
        == gateway.id
    )
    assert (
        "via_device_id"
        not in LanbonSwitch(coordinator, GATEWAY_ID, "switch:1").device_info
    )
