"""Tests for LANBON switch platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lanbon.switch import LanbonSwitch
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import GATEWAY_ID, gateway_info, snapshot

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


@pytest.mark.parametrize(
    ("child_id", "connections"),
    [
        ("child-1", set()),
        ("12345678901z", set()),
        ("aabbccddeeff", {(dr.CONNECTION_NETWORK_MAC, "aabbccddeeff")}),
    ],
)
async def test_child_metadata_and_gateway_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: MockConfigEntry,
    child_id: str,
    connections: set[tuple[str, str]],
) -> None:
    """A child uses its own metadata and the gateway registry ID."""
    coordinator = setup_integration.runtime_data
    snap = snapshot()
    child = replace(snap.devices[0], id=child_id, name="Wall Switch", model="L8-2G")
    coordinator.async_set_updated_data(replace(snap, devices=(snap.devices[0], child)))
    gateway = device_registry.async_get_device_by_identifier(
        ("lanbon", GATEWAY_ID), setup_integration.entry_id
    )
    assert gateway is not None
    info = LanbonSwitch(coordinator, child_id, "switch:1").device_info
    assert info["connections"] == connections
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


@pytest.mark.parametrize(
    ("child_id", "connections"),
    [
        ("child-1", set()),
        ("aabbccddeeff", {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}),
    ],
)
async def test_two_gateways_with_identical_child_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lanbon_client: AsyncMock,
    child_id: str,
    connections: set[tuple[str, str]],
) -> None:
    """Identical child/component IDs remain separate and control their own gateway."""
    base = snapshot()
    child = replace(base.devices[0], id=child_id)
    first_snapshot = replace(base, devices=(child,))
    second_snapshot = replace(first_snapshot, gateway_id="second-gateway")
    second_entry = MockConfigEntry(
        domain="lanbon",
        unique_id="second-gateway",
        data={
            **mock_config_entry.data,
            "host": "192.168.0.112",
            "gateway_id": "second-gateway",
        },
    )
    mock_lanbon_client.get_devices.return_value = first_snapshot
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_lanbon_client.get_devices.return_value = second_snapshot
    second_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.lanbon.LanbonClient.get_info",
        return_value=gateway_info(gateway_id="second-gateway"),
    ):
        assert await hass.config_entries.async_setup(second_entry.entry_id)
        await hass.async_block_till_done()
    first_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    second_entities = er.async_entries_for_config_entry(
        entity_registry, second_entry.entry_id
    )
    assert len(first_entities) == len(second_entities) == 1
    first, second = first_entities[0], second_entities[0]
    assert first.entity_id != second.entity_id
    assert first.unique_id != second.unique_id
    assert first.device_id != second.device_id
    first_device = device_registry.async_get(first.device_id)
    second_device = device_registry.async_get(second.device_id)
    assert first_device.identifiers != second_device.identifiers
    assert first_device.connections == second_device.connections == connections
    assert first_device.via_device_id != second_device.via_device_id
    assert first_device.config_entry_id == mock_config_entry.entry_id
    assert second_device.config_entry_id == second_entry.entry_id

    with (
        patch.object(
            mock_config_entry.runtime_data.client, "send_command"
        ) as send_first,
        patch.object(second_entry.runtime_data.client, "send_command") as send_second,
        patch.object(mock_config_entry.runtime_data, "async_request_refresh"),
        patch.object(second_entry.runtime_data, "async_request_refresh"),
    ):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": first.entity_id}, blocking=True
        )
        send_first.assert_awaited_once_with(
            child_id, "switch:1", "set_on", {"on": True}
        )
        send_second.assert_not_awaited()
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": second.entity_id}, blocking=True
        )
        send_second.assert_awaited_once_with(
            child_id, "switch:1", "set_on", {"on": False}
        )
        assert send_first.await_count == 1
