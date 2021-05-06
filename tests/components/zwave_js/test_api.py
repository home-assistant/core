"""Test the Z-Wave JS Websocket API."""
import json
from unittest.mock import patch

from zwave_js_server.const import LogLevel
from zwave_js_server.event import Event
from zwave_js_server.exceptions import InvalidNewValue, NotFoundError, SetValueFailed

from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.components.zwave_js.api import (
    COMMAND_CLASS_ID,
    CONFIG,
    ENABLED,
    ENTRY_ID,
    FILENAME,
    FORCE_CONSOLE,
    ID,
    LEVEL,
    LOG_TO_FILE,
    NODE_ID,
    OPTED_IN,
    PROPERTY,
    PROPERTY_KEY,
    TYPE,
    VALUE,
)
from homeassistant.components.zwave_js.const import (
    CONF_DATA_COLLECTION_OPTED_IN,
    DOMAIN,
)
from homeassistant.helpers import device_registry as dr


async def test_network_status(hass, integration, hass_ws_client):
    """Test the network status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {ID: 2, TYPE: "zwave_js/network_status", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result["client"]["ws_server_url"] == "ws://test:3000/zjs"
    assert result["client"]["server_version"] == "1.0.0"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/network_status", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_node_status(hass, integration, multisensor_6, hass_ws_client):
    """Test the node status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = multisensor_6
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result[NODE_ID] == 52
    assert result["ready"]
    assert result["is_routing"]
    assert not result["is_secure"]
    assert result["status"] == 1

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/node_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 99999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/node_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_add_node(
    hass, integration, client, hass_ws_client, nortek_thermostat_added_event
):
    """Test the add_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "secure": False,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion started"

    client.driver.receive_event(nortek_thermostat_added_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"
    node_details = {
        "node_id": 53,
        "status": 0,
        "ready": False,
    }
    assert msg["event"]["node"] == node_details

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "device registered"
    # Check the keys of the device item
    assert list(msg["event"]["device"]) == ["name", "id"]

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 4, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_cancel_inclusion_exclusion(hass, integration, client, hass_ws_client):
    """Test cancelling the inclusion and exclusion process."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 4, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 6, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    await ws_client.send_json(
        {ID: 7, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_remove_node(
    hass,
    integration,
    client,
    hass_ws_client,
    nortek_thermostat,
    nortek_thermostat_removed_event,
):
    """Test the remove_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="exclusion started",
        data={
            "source": "controller",
            "event": "exclusion started",
            "secure": False,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "exclusion started"

    # Add mock node to controller
    client.driver.controller.nodes[67] = nortek_thermostat

    dev_reg = dr.async_get(hass)

    # Create device registry entry for mock node
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, "3245146787-67")},
    )
    assert device is None

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 4, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_refresh_node_info(
    hass, client, integration, hass_ws_client, multisensor_6
):
    """Test that the refresh_node_info WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_info",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_info"
    assert args["nodeId"] == 52

    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 52},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview started"

    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": 52,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 52},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={"source": "node", "event": "interview failed", "nodeId": 52},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    client.async_send_command_no_wait.reset_mock()

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_info",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 9999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/refresh_node_info",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_refresh_node_values(
    hass, client, integration, hass_ws_client, multisensor_6
):
    """Test that the refresh_node_values WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_values"
    assert args["nodeId"] == 52

    client.async_send_command_no_wait.reset_mock()

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 99999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test getting non-existent entry fails
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/refresh_node_values",
            ENTRY_ID: "fake_entry_id",
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_refresh_node_cc_values(
    hass, client, integration, hass_ws_client, multisensor_6
):
    """Test that the refresh_node_cc_values WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_cc_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_cc_values"
    assert args["nodeId"] == 52
    assert args["commandClass"] == 112

    client.async_send_command_no_wait.reset_mock()

    # Test using invalid CC ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_cc_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            COMMAND_CLASS_ID: 9999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/refresh_node_cc_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 9999,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/refresh_node_cc_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_set_config_parameter(
    hass, client, hass_ws_client, multisensor_6, integration
):
    """Test the set_config_parameter service."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = None

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/set_config_parameter",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClassName": "Configuration",
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyName": "Group 2: Send battery reports",
        "propertyKey": 1,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "valueSize": 4,
            "min": 0,
            "max": 1,
            "default": 1,
            "format": 0,
            "allowManualEntry": True,
            "label": "Group 2: Send battery reports",
            "description": "Include battery information in periodic reports to Group 2",
            "isFromConfig": True,
        },
        "value": 0,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    with patch(
        "homeassistant.components.zwave_js.api.async_set_config_parameter",
    ) as set_param_mock:
        set_param_mock.side_effect = InvalidNewValue("test")
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/set_config_parameter",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 52,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "not_supported"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = NotFoundError("test")
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "zwave_js/set_config_parameter",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 52,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "not_found"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = SetValueFailed("test")
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/set_config_parameter",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 52,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "unknown_error"
        assert msg["error"]["message"] == "test"

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/set_config_parameter",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 9999,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/set_config_parameter",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )

    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_get_config_parameters(hass, integration, multisensor_6, hass_ws_client):
    """Test the get config parameters websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    node = multisensor_6

    # Test getting configuration parameter values
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/get_config_parameters",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert len(result) == 61
    key = "52-112-0-2"
    assert result[key]["property"] == 2
    assert result[key]["property_key"] is None
    assert result[key]["metadata"]["type"] == "number"
    assert result[key]["configuration_value_type"] == "enumerated"
    assert result[key]["metadata"]["states"]

    key = "52-112-0-201-255"
    assert result[key]["property_key"] == 255

    # Test getting non-existent node config params fails
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/get_config_parameters",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 99999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/get_config_parameters",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_dump_view(integration, hass_client):
    """Test the HTTP dump view."""
    client = await hass_client()
    with patch(
        "zwave_js_server.dump.dump_msgs",
        return_value=[{"hello": "world"}, {"second": "msg"}],
    ):
        resp = await client.get(f"/api/zwave_js/dump/{integration.entry_id}")
    assert resp.status == 200
    assert json.loads(await resp.text()) == [{"hello": "world"}, {"second": "msg"}]


async def test_dump_view_invalid_entry_id(integration, hass_client):
    """Test an invalid config entry id parameter."""
    client = await hass_client()
    resp = await client.get("/api/zwave_js/dump/INVALID")
    assert resp.status == 400


async def test_subscribe_logs(hass, integration, client, hass_ws_client):
    """Test the subscribe_logs websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    await ws_client.send_json(
        {ID: 1, TYPE: "zwave_js/subscribe_logs", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="logging",
        data={
            "source": "driver",
            "event": "logging",
            "message": "test",
            "formattedMessage": "test",
            "direction": ">",
            "level": "debug",
            "primaryTags": "tag",
            "secondaryTags": "tag2",
            "secondaryTagPadding": 0,
            "multiline": False,
            "timestamp": "time",
            "label": "label",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "message": ["test"],
        "level": "debug",
        "primary_tags": "tag",
        "timestamp": "time",
    }

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 2, TYPE: "zwave_js/subscribe_logs", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_update_log_config(hass, client, integration, hass_ws_client):
    """Test that the update_log_config WS API call works and that schema validation works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can set log level
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "Error"},
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {"level": "error"}

    client.async_send_command.reset_mock()

    # Test we can set logToFile to True
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LOG_TO_FILE: True, FILENAME: "/test"},
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {"logToFile": True, "filename": "/test"}

    client.async_send_command.reset_mock()

    # Test all parameters
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {
                LEVEL: "Error",
                LOG_TO_FILE: True,
                FILENAME: "/test",
                FORCE_CONSOLE: True,
                ENABLED: True,
            },
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {
        "level": "error",
        "logToFile": True,
        "filename": "/test",
        "forceConsole": True,
        "enabled": True,
    }

    client.async_send_command.reset_mock()

    # Test error when setting unrecognized log level
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "bad_log_level"},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert "error" in msg and "value must be one of" in msg["error"]["message"]

    # Test error without service data
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert "error" in msg and "must contain at least one of" in msg["error"]["message"]

    # Test error if we set logToFile to True without providing filename
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LOG_TO_FILE: True},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert (
        "error" in msg
        and "must be provided if logging to file" in msg["error"]["message"]
    )


async def test_get_log_config(hass, client, integration, hass_ws_client):
    """Test that the get_log_config WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    client.async_send_command.return_value = {
        "success": True,
        "config": {
            "enabled": True,
            "level": "error",
            "logToFile": False,
            "filename": "/test.txt",
            "forceConsole": False,
        },
    }
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/get_log_config",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    log_config = msg["result"]
    assert log_config["enabled"]
    assert log_config["level"] == LogLevel.ERROR
    assert log_config["log_to_file"] is False
    assert log_config["filename"] == "/test.txt"
    assert log_config["force_console"] is False


async def test_data_collection(hass, client, integration, hass_ws_client):
    """Test that the data collection WS API commands work."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"statisticsEnabled": False}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/data_collection_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result == {"opted_in": None, "enabled": False}

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "driver.is_statistics_enabled"
    }

    assert CONF_DATA_COLLECTION_OPTED_IN not in entry.data

    client.async_send_command.reset_mock()

    client.async_send_command.return_value = {}
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: True,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result is None

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.enable_statistics"
    assert args["applicationName"] == "Home Assistant"
    assert entry.data[CONF_DATA_COLLECTION_OPTED_IN]

    client.async_send_command.reset_mock()

    client.async_send_command.return_value = {}
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: False,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result is None

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "driver.disable_statistics"
    }
    assert not entry.data[CONF_DATA_COLLECTION_OPTED_IN]

    client.async_send_command.reset_mock()
