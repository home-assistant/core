"""Test ESPHome repairs."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from aioesphomeapi import APIClient, BinarySensorInfo, BinarySensorState, DeviceInfo
import pytest

from homeassistant.components.esphome import repairs
from homeassistant.components.esphome.const import DOMAIN
from homeassistant.components.esphome.manager import DEVICE_CONFLICT_ISSUE_FORMAT
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    get_repairs,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_create_fix_flow_raises_on_unknown_issue_id(hass: HomeAssistant) -> None:
    """Test create_fix_flow raises on unknown issue_id."""

    with pytest.raises(ValueError):
        await repairs.async_create_fix_flow(hass, "no_such_issue", None)


async def test_device_conflict_manual(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test guided manual conflict resolution."""
    disconnect_done = hass.loop.create_future()

    async def async_disconnect(*args, **kwargs) -> None:
        disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            mac_address="1122334455ab", name="test", model="esp32-iso-poe"
        )
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert "Unexpected device found" in caplog.text
    issue_id = DEVICE_CONFLICT_ISSUE_FORMAT.format(mock_config_entry.entry_id)

    issues = await get_repairs(hass, hass_ws_client)
    assert issues
    assert len(issues) == 1
    assert any(True for issue in issues if issue["issue_id"] == issue_id)

    await async_process_repairs_platforms(hass)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "ip": "192.168.1.2",
        "mac": "11:22:33:44:55:ab",
        "model": "esp32-iso-poe",
        "name": "test",
        "stored_mac": "11:22:33:44:55:aa",
    }
    assert data["type"] == FlowResultType.MENU
    assert data["step_id"] == "init"

    data = await process_repair_fix_flow(
        client, flow_id, json={"next_step_id": "manual"}
    )

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "ip": "192.168.1.2",
        "mac": "11:22:33:44:55:ab",
        "model": "esp32-iso-poe",
        "name": "test",
        "stored_mac": "11:22:33:44:55:aa",
    }
    assert data["type"] == FlowResultType.FORM
    assert data["step_id"] == "manual"

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            mac_address="11:22:33:44:55:aa", name="test", model="esp32-iso-poe"
        )
    )
    caplog.clear()
    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert "Unexpected device found" not in caplog.text
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_device_conflict_migration(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test migrating existing configuration to new hardware."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
            is_status_binary_sensor=True,
        )
    ]
    states = [BinarySensorState(key=1, state=None)]
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
    mock_config_entry = device.entry

    ent_reg_entry = entity_registry.async_get("binary_sensor.test_mybinary_sensor")
    assert ent_reg_entry
    assert ent_reg_entry.unique_id == "11:22:33:44:55:AA-binary_sensor-mybinary_sensor"
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries is not None
    for entry in entries:
        assert entry.unique_id.startswith("11:22:33:44:55:AA-")
    disconnect_done = hass.loop.create_future()

    async def async_disconnect(*args, **kwargs) -> None:
        if not disconnect_done.done():
            disconnect_done.set_result(None)

    mock_client.disconnect = async_disconnect
    new_device_info = DeviceInfo(
        mac_address="11:22:33:44:55:AB", name="test", model="esp32-iso-poe"
    )
    mock_client.device_info = AsyncMock(return_value=new_device_info)
    device.device_info = new_device_info
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    async with asyncio.timeout(1):
        await disconnect_done

    assert "Unexpected device found" in caplog.text
    issue_id = DEVICE_CONFLICT_ISSUE_FORMAT.format(mock_config_entry.entry_id)

    issues = await get_repairs(hass, hass_ws_client)
    assert issues
    assert len(issues) == 1
    assert any(True for issue in issues if issue["issue_id"] == issue_id)

    await async_process_repairs_platforms(hass)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "ip": "test.local",
        "mac": "11:22:33:44:55:ab",
        "model": "esp32-iso-poe",
        "name": "test",
        "stored_mac": "11:22:33:44:55:aa",
    }
    assert data["type"] == FlowResultType.MENU
    assert data["step_id"] == "init"

    data = await process_repair_fix_flow(
        client, flow_id, json={"next_step_id": "migrate"}
    )

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "ip": "test.local",
        "mac": "11:22:33:44:55:ab",
        "model": "esp32-iso-poe",
        "name": "test",
        "stored_mac": "11:22:33:44:55:aa",
    }
    assert data["type"] == FlowResultType.FORM
    assert data["step_id"] == "migrate"

    caplog.clear()
    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert "Unexpected device found" not in caplog.text
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    assert mock_config_entry.unique_id == "11:22:33:44:55:ab"
    ent_reg_entry = entity_registry.async_get("binary_sensor.test_mybinary_sensor")
    assert ent_reg_entry
    assert ent_reg_entry.unique_id == "11:22:33:44:55:AB-binary_sensor-mybinary_sensor"

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries is not None
    for entry in entries:
        assert entry.unique_id.startswith("11:22:33:44:55:AB-")

    dev_entry = device_registry.async_get_device(
        identifiers={}, connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:ab")}
    )
    assert dev_entry is not None

    old_dev_entry = device_registry.async_get_device(
        identifiers={}, connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:aa")}
    )
    assert old_dev_entry is None
