"""Test OpenZWave Websocket API."""
from openzwavemqtt.const import (
    ATTR_CODE_SLOT,
    ATTR_LABEL,
    ATTR_OPTIONS,
    ATTR_POSITION,
    ATTR_VALUE,
    ValueType,
)

from homeassistant.components.ozw.const import ATTR_CONFIG_PARAMETER
from homeassistant.components.ozw.lock import ATTR_USERCODE
from homeassistant.components.ozw.websocket_api import (
    ATTR_IS_AWAKE,
    ATTR_IS_BEAMING,
    ATTR_IS_FAILED,
    ATTR_IS_FLIRS,
    ATTR_IS_ROUTING,
    ATTR_IS_SECURITYV1,
    ATTR_IS_ZWAVE_PLUS,
    ATTR_NEIGHBORS,
    ATTR_NODE_BASIC_STRING,
    ATTR_NODE_BAUD_RATE,
    ATTR_NODE_GENERIC_STRING,
    ATTR_NODE_QUERY_STAGE,
    ATTR_NODE_SPECIFIC_STRING,
    ID,
    NODE_ID,
    OZW_INSTANCE,
    PARAMETER,
    SCHEMA,
    TYPE,
    VALUE,
)
from homeassistant.components.websocket_api.const import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
)

from .common import MQTTMessage, setup_ozw

from tests.async_mock import patch


async def test_websocket_api(hass, generic_data, hass_ws_client):
    """Test the ozw websocket api."""
    await setup_ozw(hass, fixture=generic_data)
    client = await hass_ws_client(hass)

    # Test instance list
    await client.send_json({ID: 4, TYPE: "ozw/get_instances"})
    msg = await client.receive_json()
    assert len(msg["result"]) == 1
    result = msg["result"][0]
    assert result[OZW_INSTANCE] == 1
    assert result["Status"] == "driverAllNodesQueried"
    assert result["OpenZWave_Version"] == "1.6.1008"

    # Test network status
    await client.send_json({ID: 5, TYPE: "ozw/network_status"})
    msg = await client.receive_json()
    result = msg["result"]

    assert result["Status"] == "driverAllNodesQueried"
    assert result[OZW_INSTANCE] == 1

    # Test node status
    await client.send_json({ID: 6, TYPE: "ozw/node_status", NODE_ID: 32})
    msg = await client.receive_json()
    result = msg["result"]

    assert result[OZW_INSTANCE] == 1
    assert result[NODE_ID] == 32
    assert result[ATTR_NODE_QUERY_STAGE] == "Complete"
    assert result[ATTR_IS_ZWAVE_PLUS]
    assert result[ATTR_IS_AWAKE]
    assert not result[ATTR_IS_FAILED]
    assert result[ATTR_NODE_BAUD_RATE] == 100000
    assert result[ATTR_IS_BEAMING]
    assert not result[ATTR_IS_FLIRS]
    assert result[ATTR_IS_ROUTING]
    assert not result[ATTR_IS_SECURITYV1]
    assert result[ATTR_NODE_BASIC_STRING] == "Routing Slave"
    assert result[ATTR_NODE_GENERIC_STRING] == "Binary Switch"
    assert result[ATTR_NODE_SPECIFIC_STRING] == "Binary Power Switch"
    assert result[ATTR_NEIGHBORS] == [1, 33, 36, 37, 39]

    await client.send_json({ID: 7, TYPE: "ozw/node_status", NODE_ID: 999})
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test node statistics
    await client.send_json({ID: 8, TYPE: "ozw/node_statistics", NODE_ID: 39})
    msg = await client.receive_json()
    result = msg["result"]

    assert result[OZW_INSTANCE] == 1
    assert result[NODE_ID] == 39
    assert result["send_count"] == 57
    assert result["sent_failed"] == 0
    assert result["retries"] == 1
    assert result["last_request_rtt"] == 26
    assert result["last_response_rtt"] == 38
    assert result["average_request_rtt"] == 29
    assert result["average_response_rtt"] == 37
    assert result["received_packets"] == 3594
    assert result["received_dup_packets"] == 12
    assert result["received_unsolicited"] == 3546

    # Test node metadata
    await client.send_json({ID: 9, TYPE: "ozw/node_metadata", NODE_ID: 39})
    msg = await client.receive_json()
    result = msg["result"]
    assert result["metadata"]["ProductPic"] == "images/aeotec/zwa002.png"

    await client.send_json({ID: 10, TYPE: "ozw/node_metadata", NODE_ID: 999})
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test network statistics
    await client.send_json({ID: 11, TYPE: "ozw/network_statistics"})
    msg = await client.receive_json()
    result = msg["result"]
    assert result["readCnt"] == 92220
    assert result[OZW_INSTANCE] == 1
    assert result["node_count"] == 5

    # Test get nodes
    await client.send_json({ID: 12, TYPE: "ozw/get_nodes"})
    msg = await client.receive_json()
    result = msg["result"]
    assert len(result) == 5
    assert result[2][ATTR_IS_AWAKE]
    assert not result[1][ATTR_IS_FAILED]

    # Test get config parameters
    await client.send_json({ID: 13, TYPE: "ozw/get_config_parameters", NODE_ID: 39})
    msg = await client.receive_json()
    result = msg["result"]
    assert len(result) == 8
    for config_param in result:
        assert config_param["type"] in (
            ValueType.LIST.value,
            ValueType.BOOL.value,
            ValueType.INT.value,
            ValueType.BYTE.value,
            ValueType.SHORT.value,
            ValueType.BITSET.value,
        )

    # Test set config parameter
    config_param = result[0]
    print(config_param)
    current_val = config_param[ATTR_VALUE]
    new_val = next(
        option[0]
        for option in config_param[SCHEMA][0][ATTR_OPTIONS]
        if option[0] != current_val
    )
    new_label = next(
        option[1]
        for option in config_param[SCHEMA][0][ATTR_OPTIONS]
        if option[1] != current_val and option[0] != new_val
    )
    await client.send_json(
        {
            ID: 14,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: config_param[ATTR_CONFIG_PARAMETER],
            VALUE: new_val,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await client.send_json(
        {
            ID: 15,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: config_param[ATTR_CONFIG_PARAMETER],
            VALUE: new_label,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # Test OZW Instance not found error
    await client.send_json(
        {ID: 16, TYPE: "ozw/get_config_parameters", OZW_INSTANCE: 999, NODE_ID: 1}
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test OZW Node not found error
    await client.send_json(
        {
            ID: 18,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 999,
            PARAMETER: 0,
            VALUE: "test",
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test parameter not found
    await client.send_json(
        {
            ID: 19,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: 45,
            VALUE: "test",
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test list value not found
    await client.send_json(
        {
            ID: 20,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: config_param[ATTR_CONFIG_PARAMETER],
            VALUE: "test",
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND

    # Test value type invalid
    await client.send_json(
        {
            ID: 21,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: 3,
            VALUE: 0,
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_SUPPORTED

    # Test invalid bitset format
    await client.send_json(
        {
            ID: 22,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: 3,
            VALUE: {ATTR_POSITION: 1, ATTR_VALUE: True, ATTR_LABEL: "test"},
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_INVALID_FORMAT

    # Test valid bitset format passes validation
    await client.send_json(
        {
            ID: 23,
            TYPE: "ozw/set_config_parameter",
            NODE_ID: 39,
            PARAMETER: 10000,
            VALUE: {ATTR_POSITION: 1, ATTR_VALUE: True},
        }
    )
    msg = await client.receive_json()
    result = msg["error"]
    assert result["code"] == ERR_NOT_FOUND


async def test_ws_locks(hass, lock_data, hass_ws_client):
    """Test lock websocket apis."""
    await setup_ozw(hass, fixture=lock_data)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            ID: 1,
            TYPE: "ozw/get_code_slots",
            NODE_ID: 10,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    await client.send_json(
        {
            ID: 2,
            TYPE: "ozw/set_usercode",
            NODE_ID: 10,
            ATTR_CODE_SLOT: 1,
            ATTR_USERCODE: "1234",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    await client.send_json(
        {
            ID: 3,
            TYPE: "ozw/clear_usercode",
            NODE_ID: 10,
            ATTR_CODE_SLOT: 1,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]


async def test_refresh_node(hass, generic_data, sent_messages, hass_ws_client):
    """Test the ozw refresh node api."""
    receive_message = await setup_ozw(hass, fixture=generic_data)
    client = await hass_ws_client(hass)

    # Send the refresh_node_info command
    await client.send_json({ID: 9, TYPE: "ozw/refresh_node_info", NODE_ID: 39})
    msg = await client.receive_json()

    assert len(sent_messages) == 1
    assert msg["success"]

    # Receive a mock status update from OZW
    message = MQTTMessage(
        topic="OpenZWave/1/node/39/",
        payload={"NodeID": 39, "NodeQueryStage": "initializing"},
    )
    message.encode()
    receive_message(message)

    # Verify we got expected data on the websocket
    msg = await client.receive_json()
    result = msg["event"]
    assert result["type"] == "node_updated"
    assert result["node_query_stage"] == "initializing"

    # Send another mock status update from OZW
    message = MQTTMessage(
        topic="OpenZWave/1/node/39/",
        payload={"NodeID": 39, "NodeQueryStage": "versions"},
    )
    message.encode()
    receive_message(message)

    # Send a mock status update for a different node
    message = MQTTMessage(
        topic="OpenZWave/1/node/35/",
        payload={"NodeID": 35, "NodeQueryStage": "fake_shouldnt_be_received"},
    )
    message.encode()
    receive_message(message)

    # Verify we received the message for node 39 but not for node 35
    msg = await client.receive_json()
    result = msg["event"]
    assert result["type"] == "node_updated"
    assert result["node_query_stage"] == "versions"


async def test_refresh_node_unsubscribe(hass, generic_data, hass_ws_client):
    """Test unsubscribing the ozw refresh node api."""
    await setup_ozw(hass, fixture=generic_data)
    client = await hass_ws_client(hass)

    with patch("openzwavemqtt.OZWOptions.listen") as mock_listen:
        # Send the refresh_node_info command
        await client.send_json({ID: 9, TYPE: "ozw/refresh_node_info", NODE_ID: 39})
        await client.receive_json()

        # Send the unsubscribe command
        await client.send_json({ID: 10, TYPE: "unsubscribe_events", "subscription": 9})
        await client.receive_json()

        assert mock_listen.return_value.called
