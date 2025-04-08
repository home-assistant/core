"""Test ESPHome repairs."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from aioesphomeapi import APIClient, DeviceInfo
import pytest

from homeassistant.components.esphome import repairs
from homeassistant.components.esphome.const import DOMAIN
from homeassistant.components.esphome.manager import DEVICE_CONFLICT_ISSUE_FORMAT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

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
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""
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
    assert data["step_id"] == "start"

    data = await process_repair_fix_flow(client, flow_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        "ip": "192.168.1.2",
        "mac": "11:22:33:44:55:ab",
        "model": "esp32-iso-poe",
        "name": "test",
        "stored_mac": "11:22:33:44:55:aa",
    }
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"
