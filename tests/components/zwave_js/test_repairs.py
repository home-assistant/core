"""Test the Z-Wave JS repairs module."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def _trigger_repair_issue(
    hass: HomeAssistant, client, multisensor_6_state
) -> Node:
    """Trigger repair issue."""
    # Create a node
    node_state = deepcopy(multisensor_6_state)
    node = Node(client, node_state)
    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": "",
        },
    )
    with patch(
        "zwave_js_server.model.node.Node.async_has_device_config_changed",
        return_value=True,
    ):
        client.driver.controller.receive_event(event)
        await hass.async_block_till_done()

    client.async_send_command_no_wait.reset_mock()

    return node


async def test_device_config_file_changed_confirm_step(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    client,
    multisensor_6_state,
    integration,
) -> None:
    """Test the device_config_file_changed issue confirm step."""
    node = await _trigger_repair_issue(hass, client, multisensor_6_state)

    client.async_send_command_no_wait.reset_mock()

    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, node)}
    )
    assert device
    issue_id = f"device_config_file_changed.{device.id}"

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == issue_id
    assert issue["translation_placeholders"] == {"device_name": device.name}

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "init"
    assert data["description_placeholders"] == {"device_name": device.name}

    # Show menu
    data = await process_repair_fix_flow(http_client, flow_id)

    assert data["type"] == "menu"

    # Apply fix
    data = await process_repair_fix_flow(
        http_client, flow_id, json={"next_step_id": "confirm"}
    )

    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    assert client.async_send_command_no_wait.call_args[0][0] == {
        "command": "node.refresh_info",
        "nodeId": node.node_id,
    }

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


async def test_device_config_file_changed_ignore_step(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    client,
    multisensor_6_state,
    integration,
) -> None:
    """Test the device_config_file_changed issue ignore step."""
    node = await _trigger_repair_issue(hass, client, multisensor_6_state)

    client.async_send_command_no_wait.reset_mock()

    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, node)}
    )
    assert device
    issue_id = f"device_config_file_changed.{device.id}"

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == issue_id
    assert issue["translation_placeholders"] == {"device_name": device.name}

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "init"
    assert data["description_placeholders"] == {"device_name": device.name}

    # Show menu
    data = await process_repair_fix_flow(http_client, flow_id)

    assert data["type"] == "menu"

    # Ignore the issue
    data = await process_repair_fix_flow(
        http_client, flow_id, json={"next_step_id": "ignore"}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "issue_ignored"
    assert data["description_placeholders"] == {"device_name": device.name}

    await hass.async_block_till_done()

    assert len(client.async_send_command_no_wait.call_args_list) == 0

    # Assert the issue still exists but is ignored
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert msg["result"]["issues"][0].get("dismissed_version") is not None


@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.zwave_js.issues.invalid_issue.title"],
)
async def test_invalid_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    integration,
) -> None:
    """Test the invalid issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "invalid_issue_id",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_issue",
    )

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == "invalid_issue_id"

    data = await start_repair_fix_flow(http_client, DOMAIN, "invalid_issue_id")

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Apply fix
    data = await process_repair_fix_flow(http_client, flow_id)

    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


async def test_abort_confirm(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    client,
    multisensor_6_state,
    integration,
) -> None:
    """Test aborting device_config_file_changed issue in confirm step."""
    node = await _trigger_repair_issue(hass, client, multisensor_6_state)

    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, node)}
    )
    assert device
    issue_id = f"device_config_file_changed.{device.id}"

    await async_process_repairs_platforms(hass)
    await hass_ws_client(hass)
    http_client = await hass_client()

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "init"

    # Unload config entry so we can't connect to the node
    await hass.config_entries.async_unload(integration.entry_id)

    # Apply fix
    data = await process_repair_fix_flow(
        http_client, flow_id, json={"next_step_id": "confirm"}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "cannot_connect"
    assert data["description_placeholders"] == {"device_name": device.name}


@pytest.mark.usefixtures("client")
async def test_migrate_unique_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the migrate unique id flow."""
    old_unique_id = "123456789"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://test.org",
        },
        unique_id=old_unique_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    issue_id = issue["issue_id"]
    assert issue_id == f"migrate_unique_id.{config_entry.entry_id}"

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "config_entry_title": "Z-Wave JS",
        "controller_model": "ZW090",
        "new_unique_id": "3245146787",
        "old_unique_id": old_unique_id,
    }

    # Apply fix
    data = await process_repair_fix_flow(http_client, flow_id)

    assert data["type"] == "create_entry"
    assert config_entry.unique_id == "3245146787"

    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


@pytest.mark.usefixtures("client")
async def test_migrate_unique_id_missing_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the migrate unique id flow with missing config entry."""
    old_unique_id = "123456789"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://test.org",
        },
        unique_id=old_unique_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    issue_id = issue["issue_id"]
    assert issue_id == f"migrate_unique_id.{config_entry.entry_id}"

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert not hass.config_entries.async_get_entry(config_entry.entry_id)

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "config_entry_title": "Z-Wave JS",
        "controller_model": "ZW090",
        "new_unique_id": "3245146787",
        "old_unique_id": old_unique_id,
    }

    # Apply fix
    data = await process_repair_fix_flow(http_client, flow_id)

    assert data["type"] == "create_entry"

    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0
