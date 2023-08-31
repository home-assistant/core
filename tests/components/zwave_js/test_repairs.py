"""Test the Z-Wave JS repairs module."""
from copy import deepcopy
from http import HTTPStatus
from unittest.mock import patch

from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.issue_registry as ir

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_device_config_file_changed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    client,
    multisensor_6_state,
    integration,
) -> None:
    """Test the device_config_file_changed issue."""
    dev_reg = dr.async_get(hass)
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

    device = dev_reg.async_get_device(identifiers={get_device_id(client.driver, node)})
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

    url = RepairsFlowIndexView.url
    resp = await http_client.post(url, json={"handler": DOMAIN, "issue_id": issue_id})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Apply fix
    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await http_client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

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

    url = RepairsFlowIndexView.url
    resp = await http_client.post(
        url, json={"handler": DOMAIN, "issue_id": "invalid_issue_id"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Apply fix
    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await http_client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0
