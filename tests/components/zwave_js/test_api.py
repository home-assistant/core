"""Test the Z-Wave JS Websocket API."""
import json
from unittest.mock import patch

import pytest
from zwave_js_server.const import CommandClass, InclusionStrategy, LogLevel
from zwave_js_server.event import Event
from zwave_js_server.exceptions import (
    FailedCommand,
    FailedZWaveCommand,
    InvalidNewValue,
    NotFoundError,
    SetValueFailed,
)
from zwave_js_server.model.value import _get_value_id_from_dict, get_value_id

from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.components.zwave_js.api import (
    COMMAND_CLASS_ID,
    CONFIG,
    ENABLED,
    ENTRY_ID,
    ERR_NOT_LOADED,
    FILENAME,
    FORCE_CONSOLE,
    ID,
    LEVEL,
    LOG_TO_FILE,
    NODE_ID,
    OPTED_IN,
    PROPERTY,
    PROPERTY_KEY,
    SECURE,
    TYPE,
    VALUE,
)
from homeassistant.components.zwave_js.const import (
    CONF_DATA_COLLECTION_OPTED_IN,
    DOMAIN,
)
from homeassistant.helpers import device_registry as dr

from .common import PROPERTY_ULTRAVIOLET


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
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_node_status(hass, multisensor_6, integration, hass_ws_client):
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
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_node_state(hass, multisensor_6, integration, hass_ws_client):
    """Test the node_state websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = multisensor_6

    # Update a value and ensure it is reflected in the node state
    value_id = get_value_id(node, CommandClass.SENSOR_MULTILEVEL, PROPERTY_ULTRAVIOLET)
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": PROPERTY_ULTRAVIOLET,
                "newValue": 1,
                "prevValue": 0,
                "propertyName": PROPERTY_ULTRAVIOLET,
            },
        },
    )
    node.receive_event(event)

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_state",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    # Assert that the data returned doesn't match the stale node state data
    assert msg["result"] != node.data

    # Replace data for the value we updated and assert the new node data is the same
    # as what's returned
    updated_node_data = node.data.copy()
    for n, value in enumerate(updated_node_data["values"]):
        if _get_value_id_from_dict(node, value) == value_id:
            updated_node_data["values"][n] = node.values[value_id].data.copy()
    assert msg["result"] == updated_node_data

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/node_state",
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
            TYPE: "zwave_js/node_state",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_node_metadata(hass, wallmote_central_scene, integration, hass_ws_client):
    """Test the node metadata websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = wallmote_central_scene
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_metadata",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result[NODE_ID] == 35
    assert result["inclusion"] == (
        "To add the ZP3111 to the Z-Wave network (inclusion), place the Z-Wave "
        "primary controller into inclusion mode. Press the Program Switch of ZP3111 "
        "for sending the NIF. After sending NIF, Z-Wave will send the auto inclusion, "
        "otherwise, ZP3111 will go to sleep after 20 seconds."
    )
    assert result["exclusion"] == (
        "To remove the ZP3111 from the Z-Wave network (exclusion), place the Z-Wave "
        "primary controller into \u201cexclusion\u201d mode, and following its "
        "instruction to delete the ZP3111 to the controller. Press the Program Switch "
        "of ZP3111 once to be excluded."
    )
    assert result["reset"] == (
        "Remove cover to triggered tamper switch, LED flash once & send out Alarm "
        "Report. Press Program Switch 10 times within 10 seconds, ZP3111 will send "
        "the \u201cDevice Reset Locally Notification\u201d command and reset to the "
        "factory default. (Remark: This is to be used only in the case of primary "
        "controller being inoperable or otherwise unavailable.)"
    )
    assert result["manual"] == (
        "https://products.z-wavealliance.org/ProductManual/File?folder=&filename=MarketCertificationFiles/2479/ZP3111-5_R2_20170316.pdf"
    )
    assert not result["wakeup"]
    assert (
        result["device_database_url"]
        == "https://devices.zwave-js.io/?jumpTo=0x0086:0x0002:0x0082:0.0"
    )

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/node_metadata",
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
            TYPE: "zwave_js/node_metadata",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_ping_node(
    hass, wallmote_central_scene, integration, client, hass_ws_client
):
    """Test the ping_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    node = wallmote_central_scene

    client.async_send_command.return_value = {"responded": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/ping_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/ping_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 99999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_ping",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "zwave_js/ping_node",
                ENTRY_ID: entry.entry_id,
                NODE_ID: node.node_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/ping_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_add_node_secure(
    hass, nortek_thermostat_added_event, integration, client, hass_ws_client
):
    """Test the add_node websocket command with secure flag."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 1, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id, SECURE: True}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {"strategy": InclusionStrategy.SECURITY_S0},
    }

    client.async_send_command.reset_mock()


async def test_add_node(
    hass, nortek_thermostat_added_event, integration, client, hass_ws_client
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

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {"strategy": InclusionStrategy.INSECURE},
    }

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
        "node_id": 67,
        "status": 0,
        "ready": False,
    }
    assert msg["event"]["node"] == node_details

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "device registered"
    # Check the keys of the device item
    assert list(msg["event"]["device"]) == ["name", "id", "manufacturer", "model"]

    # Test receiving interview events
    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 67},
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
            "nodeId": 67,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={"source": "node", "event": "interview failed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_begin_inclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/add_node",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_stop_inclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/stop_inclusion",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_stop_exclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/stop_exclusion",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 8, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {ID: 9, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_begin_exclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/remove_node",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_replace_failed_node_secure(
    hass,
    nortek_thermostat,
    integration,
    client,
    hass_ws_client,
):
    """Test the replace_failed_node websocket command with secure flag."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    dev_reg = dr.async_get(hass)

    # Create device registry entry for mock node
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/replace_failed_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
            SECURE: True,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": nortek_thermostat.node_id,
        "options": {"strategy": InclusionStrategy.SECURITY_S0},
    }

    client.async_send_command.reset_mock()


async def test_replace_failed_node(
    hass,
    nortek_thermostat,
    integration,
    client,
    hass_ws_client,
    nortek_thermostat_added_event,
    nortek_thermostat_removed_event,
):
    """Test the replace_failed_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    dev_reg = dr.async_get(hass)

    # Create device registry entry for mock node
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    client.async_send_command.return_value = {"success": True}

    # Order of events we receive for a successful replacement is `inclusion started`,
    # `inclusion stopped`, `node removed`, `node added`, then interview stages.
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/replace_failed_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": nortek_thermostat.node_id,
        "options": {"strategy": InclusionStrategy.INSECURE},
    }

    client.async_send_command.reset_mock()

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

    event = Event(
        type="inclusion stopped",
        data={
            "source": "controller",
            "event": "inclusion stopped",
            "secure": False,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion stopped"

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, "3245146787-67")},
    )
    assert device is None

    client.driver.receive_event(nortek_thermostat_added_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"
    node_details = {
        "node_id": 67,
        "status": 0,
        "ready": False,
    }
    assert msg["event"]["node"] == node_details

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "device registered"
    # Check the keys of the device item
    assert list(msg["event"]["device"]) == ["name", "id", "manufacturer", "model"]

    # Test receiving interview events
    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 67},
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
            "nodeId": 67,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={"source": "node", "event": "interview failed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_replace_failed_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/replace_failed_node",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 67,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/replace_failed_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_remove_failed_node(
    hass,
    nortek_thermostat,
    integration,
    client,
    hass_ws_client,
    nortek_thermostat_removed_event,
):
    """Test the remove_failed_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/remove_failed_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_remove_failed_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/remove_failed_node",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 67,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/remove_failed_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_begin_healing_network(
    hass,
    integration,
    client,
    hass_ws_client,
):
    """Test the begin_healing_network websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/begin_healing_network",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_begin_healing_network",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/begin_healing_network",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/begin_healing_network",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_heal_network_progress(
    hass, integration, client, hass_ws_client
):
    """Test the subscribe_heal_network_progress command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_heal_network_progress",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    # Fire heal network progress
    event = Event(
        "heal network progress",
        {
            "source": "controller",
            "event": "heal network progress",
            "progress": {67: "pending"},
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "heal network progress"
    assert msg["event"]["heal_node_status"] == {"67": "pending"}

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/subscribe_heal_network_progress",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_heal_network_progress_initial_value(
    hass, integration, client, hass_ws_client
):
    """Test subscribe_heal_network_progress command when heal network in progress."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    assert not client.driver.controller.heal_network_progress

    # Fire heal network progress before sending heal network progress command
    event = Event(
        "heal network progress",
        {
            "source": "controller",
            "event": "heal network progress",
            "progress": {67: "pending"},
        },
    )
    client.driver.controller.receive_event(event)

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_heal_network_progress",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"67": "pending"}


async def test_stop_healing_network(
    hass,
    integration,
    client,
    hass_ws_client,
):
    """Test the stop_healing_network websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/stop_healing_network",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_stop_healing_network",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/stop_healing_network",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/stop_healing_network",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_heal_node(
    hass,
    integration,
    client,
    hass_ws_client,
):
    """Test the heal_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/heal_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.controller.Controller.async_heal_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/heal_node",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 67,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/heal_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 67,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_info(
    hass, client, multisensor_6, integration, hass_ws_client
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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_info",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
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
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/refresh_node_info",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_values(
    hass, client, multisensor_6, integration, hass_ws_client
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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_values",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/refresh_node_values",
                ENTRY_ID: entry.entry_id,
                NODE_ID: 52,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/refresh_node_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_cc_values(
    hass, client, multisensor_6, integration, hass_ws_client
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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_cc_values",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
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
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/refresh_node_cc_values",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


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

    # Test that hex strings are accepted and converted as expected
    client.async_send_command_no_wait.return_value = None

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/set_config_parameter",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 52,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: "0x1",
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
        assert msg["error"]["code"] == "not_supported"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = NotFoundError("test")
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
        assert msg["error"]["code"] == "not_found"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = SetValueFailed("test")
        await ws_client.send_json(
            {
                ID: 5,
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
            ID: 6,
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

    # Test FailedZWaveCommand is caught
    with patch(
        "homeassistant.components.zwave_js.api.async_set_config_parameter",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
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
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 8,
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
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_config_parameters(hass, multisensor_6, integration, hass_ws_client):
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
    assert msg["error"]["code"] == ERR_NOT_LOADED


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


async def test_version_info(hass, integration, hass_ws_client, version_state):
    """Test the HTTP dump node view."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    version_info = {
        "driver_version": version_state["driverVersion"],
        "server_version": version_state["serverVersion"],
        "min_schema_version": 0,
        "max_schema_version": 0,
    }

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/version_info",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"] == version_info

    # Test getting non-existent entry fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/version_info",
            ENTRY_ID: "INVALID",
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
            TYPE: "zwave_js/version_info",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_firmware_upload_view(
    hass, multisensor_6, integration, hass_client, firmware_file
):
    """Test the HTTP firmware upload view."""
    client = await hass_client()
    with patch(
        "homeassistant.components.zwave_js.api.begin_firmware_update",
    ) as mock_cmd:
        resp = await client.post(
            f"/api/zwave_js/firmware/upload/{integration.entry_id}/{multisensor_6.node_id}",
            data={"file": firmware_file},
        )
        assert mock_cmd.call_args[0][1:4] == (multisensor_6, "file", bytes(10))
        assert json.loads(await resp.text()) is None


async def test_firmware_upload_view_failed_command(
    hass, multisensor_6, integration, hass_client, firmware_file
):
    """Test failed command for the HTTP firmware upload view."""
    client = await hass_client()
    with patch(
        "homeassistant.components.zwave_js.api.begin_firmware_update",
        side_effect=FailedCommand("test", "test"),
    ):
        resp = await client.post(
            f"/api/zwave_js/firmware/upload/{integration.entry_id}/{multisensor_6.node_id}",
            data={"file": firmware_file},
        )
        assert resp.status == 400


async def test_firmware_upload_view_invalid_payload(
    hass, multisensor_6, integration, hass_client
):
    """Test an invalid payload for the HTTP firmware upload view."""
    client = await hass_client()
    resp = await client.post(
        f"/api/zwave_js/firmware/upload/{integration.entry_id}/{multisensor_6.node_id}",
        data={"wrong_key": bytes(10)},
    )
    assert resp.status == 400


@pytest.mark.parametrize(
    "method, url",
    [("get", "/api/zwave_js/dump/{}")],
)
async def test_view_non_admin_user(
    integration, hass_client, hass_admin_user, method, url
):
    """Test config entry level views for non-admin users."""
    client = await hass_client()
    # Verify we require admin user
    hass_admin_user.groups = []
    resp = await client.request(method, url.format(integration.entry_id))
    assert resp.status == 401


@pytest.mark.parametrize(
    "method, url",
    [("post", "/api/zwave_js/firmware/upload/{}/{}")],
)
async def test_node_view_non_admin_user(
    multisensor_6, integration, hass_client, hass_admin_user, method, url
):
    """Test node level views for non-admin users."""
    client = await hass_client()
    # Verify we require admin user
    hass_admin_user.groups = []
    resp = await client.request(
        method, url.format(integration.entry_id, multisensor_6.node_id)
    )
    assert resp.status == 401


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/api/zwave_js/dump/INVALID"),
        ("post", "/api/zwave_js/firmware/upload/INVALID/1"),
    ],
)
async def test_view_invalid_entry_id(integration, hass_client, method, url):
    """Test an invalid config entry id parameter."""
    client = await hass_client()
    resp = await client.request(method, url)
    assert resp.status == 400


@pytest.mark.parametrize(
    "method, url",
    [("post", "/api/zwave_js/firmware/upload/{}/111")],
)
async def test_view_invalid_node_id(integration, hass_client, method, url):
    """Test an invalid config entry id parameter."""
    client = await hass_client()
    resp = await client.request(method, url.format(integration.entry_id))
    assert resp.status == 404


async def test_subscribe_log_updates(hass, integration, client, hass_ws_client):
    """Test the subscribe_log_updates websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    await ws_client.send_json(
        {ID: 1, TYPE: "zwave_js/subscribe_log_updates", ENTRY_ID: entry.entry_id}
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
        "type": "log_message",
        "log_message": {
            "message": ["test"],
            "level": "debug",
            "primary_tags": "tag",
            "timestamp": "time",
        },
    }

    event = Event(
        type="log config updated",
        data={
            "source": "driver",
            "event": "log config updated",
            "config": {
                "enabled": False,
                "level": "error",
                "logToFile": True,
                "filename": "test",
                "forceConsole": True,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "type": "log_config",
        "log_config": {
            "enabled": False,
            "level": "error",
            "log_to_file": True,
            "filename": "test",
            "force_console": True,
        },
    }

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_start_listening_logs",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/subscribe_log_updates",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/subscribe_log_updates", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_update_log_config",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/update_log_config",
                ENTRY_ID: entry.entry_id,
                CONFIG: {LEVEL: "Error"},
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 8,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "Error"},
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_log_config(hass, client, integration, hass_ws_client):
    """Test that the get_log_config WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
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
    assert log_config["level"] == LogLevel.INFO
    assert log_config["log_to_file"] is False
    assert log_config["filename"] == ""
    assert log_config["force_console"] is False

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/get_log_config",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


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

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_is_statistics_enabled",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/data_collection_status",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_enable_statistics",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "zwave_js/update_data_collection_preference",
                ENTRY_ID: entry.entry_id,
                OPTED_IN: True,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/data_collection_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: True,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_abort_firmware_update(
    hass, client, multisensor_6, integration, hass_ws_client
):
    """Test that the abort_firmware_update WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = {}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/abort_firmware_update",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.abort_firmware_update"
    assert args["nodeId"] == multisensor_6.node_id

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_abort_firmware_update",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/abort_firmware_update",
                ENTRY_ID: entry.entry_id,
                NODE_ID: multisensor_6.node_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/abort_firmware_update",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_abort_firmware_update_failures(
    hass, integration, multisensor_6, client, hass_ws_client
):
    """Test failures for the abort_firmware_update websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/abort_firmware_update",
            ENTRY_ID: "fake_entry_id",
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with improper node ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/abort_firmware_update",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id + 100,
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
            TYPE: "zwave_js/abort_firmware_update",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_firmware_update_status(
    hass, integration, multisensor_6, client, hass_ws_client
):
    """Test the subscribe_firmware_update_status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": multisensor_6.node_id,
            "sentFragments": 1,
            "totalFragments": 10,
        },
    )
    multisensor_6.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update progress",
        "sent_fragments": 1,
        "total_fragments": 10,
    }

    event = Event(
        type="firmware update finished",
        data={
            "source": "node",
            "event": "firmware update finished",
            "nodeId": multisensor_6.node_id,
            "status": 255,
            "waitTime": 10,
        },
    )
    multisensor_6.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update finished",
        "status": 255,
        "wait_time": 10,
    }


async def test_subscribe_firmware_update_status_initial_value(
    hass, integration, multisensor_6, client, hass_ws_client
):
    """Test subscribe_firmware_update_status websocket command with in progress update."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    assert multisensor_6.firmware_update_progress is None

    # Send a firmware update progress event before the WS command
    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": multisensor_6.node_id,
            "sentFragments": 1,
            "totalFragments": 10,
        },
    )
    multisensor_6.receive_event(event)

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"sent_fragments": 1, "total_fragments": 10}


async def test_subscribe_firmware_update_status_failures(
    hass, integration, multisensor_6, client, hass_ws_client
):
    """Test failures for the subscribe_firmware_update_status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            ENTRY_ID: "fake_entry_id",
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with improper node ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id + 100,
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
            TYPE: "zwave_js/subscribe_firmware_update_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_check_for_config_updates(hass, client, integration, hass_ws_client):
    """Test that the check_for_config_updates WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    client.async_send_command.return_value = {
        "updateAvailable": True,
        "newVersion": "test",
    }
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    config_update = msg["result"]
    assert config_update["update_available"]
    assert config_update["new_version"] == "test"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_check_for_config_updates",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/check_for_config_updates",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_install_config_update(hass, client, integration, hass_ws_client):
    """Test that the install_config_update WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_install_config_update",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/install_config_update",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "Z-Wave error 1: error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_subscribe_controller_statistics(
    hass, integration, client, hass_ws_client
):
    """Test the subscribe_controller_statistics command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "messages_tx": 0,
        "messages_rx": 0,
        "messages_dropped_tx": 0,
        "messages_dropped_rx": 0,
        "nak": 0,
        "can": 0,
        "timeout_ack": 0,
        "timout_response": 0,
        "timeout_callback": 0,
    }

    # Fire statistics updated
    event = Event(
        "statistics updated",
        {
            "source": "controller",
            "event": "statistics updated",
            "statistics": {
                "messagesTX": 1,
                "messagesRX": 1,
                "messagesDroppedTX": 1,
                "messagesDroppedRX": 1,
                "NAK": 1,
                "CAN": 1,
                "timeoutACK": 1,
                "timeoutResponse": 1,
                "timeoutCallback": 1,
            },
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "statistics updated",
        "source": "controller",
        "messages_tx": 1,
        "messages_rx": 1,
        "messages_dropped_tx": 1,
        "messages_dropped_rx": 1,
        "nak": 1,
        "can": 1,
        "timeout_ack": 1,
        "timout_response": 1,
        "timeout_callback": 1,
    }

    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: "fake_entry_id",
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
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_node_statistics(
    hass, multisensor_6, integration, client, hass_ws_client
):
    """Test the subscribe_node_statistics command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_node_statistics",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "commands_tx": 0,
        "commands_rx": 0,
        "commands_dropped_tx": 0,
        "commands_dropped_rx": 0,
        "timeout_response": 0,
    }

    # Fire statistics updated
    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": multisensor_6.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 1,
                "commandsDroppedTX": 1,
                "commandsDroppedRX": 1,
                "timeoutResponse": 1,
            },
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "statistics updated",
        "source": "node",
        "node_id": multisensor_6.node_id,
        "commands_tx": 1,
        "commands_rx": 1,
        "commands_dropped_tx": 1,
        "commands_dropped_rx": 1,
        "timeout_response": 1,
    }

    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_node_statistics",
            ENTRY_ID: "fake_entry_id",
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with improper node ID fails
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_node_statistics",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id + 100,
        }
    )
    msg = await ws_client.receive_json()

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/subscribe_node_statistics",
            ENTRY_ID: entry.entry_id,
            NODE_ID: multisensor_6.node_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED
