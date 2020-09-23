"""Test OpenZWave Websocket API."""
from unittest.mock import patch

from openzwavemqtt.const import (
    ATTR_CODE_SLOT,
    ATTR_LABEL,
    ATTR_OPTIONS,
    ATTR_POSITION,
    ATTR_VALUE,
    ValueType,
)
import pytest

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
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_get_registry as async_get_device_registry,
)
from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    async_get_registry as async_get_entity_registry,
)

from .common import MQTTMessage, setup_ozw

from tests.common import MockConfigEntry, mock_device_registry, mock_registry

ZWAVE_SOURCE_NODE_DEVICE_ID = "zwave_source_node_device_id"
ZWAVE_SOURCE_NODE_DEVICE_NAME = "Z-Wave Source Node Device"
ZWAVE_SOURCE_NODE_DEVICE_AREA = "Z-Wave Source Node Area"
ZWAVE_SOURCE_ENTITY = "sensor.zwave_source_node"
ZWAVE_SOURCE_NODE_UNIQUE_ID = "10-4321"
ZWAVE_BATTERY_DEVICE_ID = "zwave_battery_device_id"
ZWAVE_BATTERY_DEVICE_NAME = "Z-Wave Battery Device"
ZWAVE_BATTERY_DEVICE_AREA = "Z-Wave Battery Area"
ZWAVE_BATTERY_ENTITY = "sensor.zwave_battery_level"
ZWAVE_BATTERY_UNIQUE_ID = "36-1234"
ZWAVE_BATTERY_NAME = "Z-Wave Battery Level"
ZWAVE_BATTERY_ICON = "mdi:zwave-test-battery"
ZWAVE_POWER_DEVICE_ID = "zwave_power_device_id"
ZWAVE_POWER_DEVICE_NAME = "Z-Wave Power Device"
ZWAVE_POWER_DEVICE_AREA = "Z-Wave Power Area"
ZWAVE_POWER_ENTITY = "sensor.zwave_power"
ZWAVE_POWER_UNIQUE_ID = "32-5678"
ZWAVE_POWER_NAME = "Z-Wave Power"
ZWAVE_POWER_ICON = "mdi:zwave-test-power"


@pytest.fixture(name="zwave_migration_data")
def zwave_migration_data_fixture(hass):
    """Return mock zwave migration data."""
    zwave_source_node_device = DeviceEntry(
        id=ZWAVE_SOURCE_NODE_DEVICE_ID,
        name_by_user=ZWAVE_SOURCE_NODE_DEVICE_NAME,
        area_id=ZWAVE_SOURCE_NODE_DEVICE_AREA,
    )
    zwave_source_node_entry = RegistryEntry(
        entity_id=ZWAVE_SOURCE_ENTITY,
        unique_id=ZWAVE_SOURCE_NODE_UNIQUE_ID,
        platform="zwave",
        name="Z-Wave Source Node",
    )
    zwave_battery_device = DeviceEntry(
        id=ZWAVE_BATTERY_DEVICE_ID,
        name_by_user=ZWAVE_BATTERY_DEVICE_NAME,
        area_id=ZWAVE_BATTERY_DEVICE_AREA,
    )
    zwave_battery_entry = RegistryEntry(
        entity_id=ZWAVE_BATTERY_ENTITY,
        unique_id=ZWAVE_BATTERY_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_BATTERY_NAME,
        icon=ZWAVE_BATTERY_ICON,
    )
    zwave_power_device = DeviceEntry(
        id=ZWAVE_POWER_DEVICE_ID,
        name_by_user=ZWAVE_POWER_DEVICE_NAME,
        area_id=ZWAVE_POWER_DEVICE_AREA,
    )
    zwave_power_entry = RegistryEntry(
        entity_id=ZWAVE_POWER_ENTITY,
        unique_id=ZWAVE_POWER_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_POWER_NAME,
        icon=ZWAVE_POWER_ICON,
    )
    zwave_migration_data = {
        ZWAVE_SOURCE_NODE_UNIQUE_ID: {
            "node_id": 10,
            "node_instance": 1,
            "device_id": zwave_source_node_device.id,
            "command_class": 113,
            "command_class_label": "SourceNodeId",
            "value_index": 2,
            "unique_id": ZWAVE_SOURCE_NODE_UNIQUE_ID,
            "entity_entry": zwave_source_node_entry,
        },
        ZWAVE_BATTERY_UNIQUE_ID: {
            "node_id": 36,
            "node_instance": 1,
            "device_id": zwave_battery_device.id,
            "command_class": 128,
            "command_class_label": "Battery Level",
            "value_index": 0,
            "unique_id": ZWAVE_BATTERY_UNIQUE_ID,
            "entity_entry": zwave_battery_entry,
        },
        ZWAVE_POWER_UNIQUE_ID: {
            "node_id": 32,
            "node_instance": 1,
            "device_id": zwave_power_device.id,
            "command_class": 50,
            "command_class_label": "Power",
            "value_index": 8,
            "unique_id": ZWAVE_POWER_UNIQUE_ID,
            "entity_entry": zwave_power_entry,
        },
    }

    mock_device_registry(
        hass,
        {
            zwave_source_node_device.id: zwave_source_node_device,
            zwave_battery_device.id: zwave_battery_device,
            zwave_power_device.id: zwave_power_device,
        },
    )
    mock_registry(
        hass,
        {
            ZWAVE_SOURCE_ENTITY: zwave_source_node_entry,
            ZWAVE_BATTERY_ENTITY: zwave_battery_entry,
            ZWAVE_POWER_ENTITY: zwave_power_entry,
        },
    )

    return zwave_migration_data


@pytest.fixture(name="zwave_integration")
def zwave_integration_fixture(hass, zwave_migration_data):
    """Mock the zwave integration."""
    hass.config.components.add("zwave")
    zwave_config_entry = MockConfigEntry(domain="zwave", data={"usb_path": "/dev/test"})
    zwave_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zwave.async_get_ozw_migration_data",
        return_value=zwave_migration_data,
    ):
        yield zwave_config_entry


async def test_migrate_zwave(hass, migration_data, hass_ws_client, zwave_integration):
    """Test the zwave to ozw migration websocket api."""
    await setup_ozw(hass, fixture=migration_data)
    client = await hass_ws_client(hass)

    assert hass.config_entries.async_entries("zwave")

    await client.send_json({ID: 5, TYPE: "ozw/migrate_zwave", "dry_run": False})
    msg = await client.receive_json()
    result = msg["result"]

    migration_entity_map = {
        ZWAVE_BATTERY_ENTITY: "sensor.water_sensor_6_battery_level",
        ZWAVE_POWER_ENTITY: "sensor.smart_plug_electric_w",
    }

    assert result["zwave_entity_ids"] == [
        ZWAVE_SOURCE_ENTITY,
        ZWAVE_BATTERY_ENTITY,
        ZWAVE_POWER_ENTITY,
    ]
    assert result["ozw_entity_ids"] == [
        "sensor.smart_plug_electric_w",
        "sensor.water_sensor_6_battery_level",
    ]
    assert result["migration_entity_map"] == migration_entity_map
    assert result["migrated"] is True

    dev_reg = await async_get_device_registry(hass)
    ent_reg = await async_get_entity_registry(hass)

    # check the device registry migration

    # check that the migrated entries have correct attributes
    battery_entry = dev_reg.async_get_device(
        identifiers={("ozw", "1.36.1")}, connections=set()
    )
    assert battery_entry.name_by_user == ZWAVE_BATTERY_DEVICE_NAME
    assert battery_entry.area_id == ZWAVE_BATTERY_DEVICE_AREA
    power_entry = dev_reg.async_get_device(
        identifiers={("ozw", "1.32.1")}, connections=set()
    )
    assert power_entry.name_by_user == ZWAVE_POWER_DEVICE_NAME
    assert power_entry.area_id == ZWAVE_POWER_DEVICE_AREA

    migration_device_map = {
        ZWAVE_BATTERY_DEVICE_ID: battery_entry.id,
        ZWAVE_POWER_DEVICE_ID: power_entry.id,
    }

    assert result["migration_device_map"] == migration_device_map

    # check the entity registry migration

    # these should have been migrated and no longer present under that id
    assert not ent_reg.async_is_registered("sensor.water_sensor_6_battery_level")
    assert not ent_reg.async_is_registered("sensor.smart_plug_electric_w")

    # this one should not have been migrated and is still in the registry
    assert ent_reg.async_is_registered(ZWAVE_SOURCE_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_SOURCE_ENTITY)
    assert source_entry.unique_id == ZWAVE_SOURCE_NODE_UNIQUE_ID

    # these are the new entity_ids of the two ozw entities
    assert ent_reg.async_is_registered(ZWAVE_BATTERY_ENTITY)
    assert ent_reg.async_is_registered(ZWAVE_POWER_ENTITY)

    # check that the migrated entries have correct attributes
    battery_entry = ent_reg.async_get(ZWAVE_BATTERY_ENTITY)
    assert battery_entry.unique_id == "1-36-610271249"
    assert battery_entry.name == ZWAVE_BATTERY_NAME
    assert battery_entry.icon == ZWAVE_BATTERY_ICON
    power_entry = ent_reg.async_get(ZWAVE_POWER_ENTITY)
    assert power_entry.unique_id == "1-32-562950495305746"
    assert power_entry.name == ZWAVE_POWER_NAME
    assert power_entry.icon == ZWAVE_POWER_ICON

    # check that the zwave config entry has been removed
    assert not hass.config_entries.async_entries("zwave")

    # Check that the zwave integration fails entry setup after migration
    zwave_config_entry = MockConfigEntry(domain="zwave")
    zwave_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(zwave_config_entry.entry_id)


async def test_migrate_zwave_dry_run(
    hass, migration_data, hass_ws_client, zwave_integration
):
    """Test the zwave to ozw migration websocket api dry run."""
    await setup_ozw(hass, fixture=migration_data)
    client = await hass_ws_client(hass)

    await client.send_json({ID: 5, TYPE: "ozw/migrate_zwave"})
    msg = await client.receive_json()
    result = msg["result"]

    migration_entity_map = {
        ZWAVE_BATTERY_ENTITY: "sensor.water_sensor_6_battery_level",
        ZWAVE_POWER_ENTITY: "sensor.smart_plug_electric_w",
    }

    assert result["zwave_entity_ids"] == [
        ZWAVE_SOURCE_ENTITY,
        ZWAVE_BATTERY_ENTITY,
        ZWAVE_POWER_ENTITY,
    ]
    assert result["ozw_entity_ids"] == [
        "sensor.smart_plug_electric_w",
        "sensor.water_sensor_6_battery_level",
    ]
    assert result["migration_entity_map"] == migration_entity_map
    assert result["migrated"] is False

    ent_reg = await async_get_entity_registry(hass)

    # no real migration should have been done
    assert ent_reg.async_is_registered("sensor.water_sensor_6_battery_level")
    assert ent_reg.async_is_registered("sensor.smart_plug_electric_w")

    assert ent_reg.async_is_registered(ZWAVE_SOURCE_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_SOURCE_ENTITY)
    assert source_entry.unique_id == ZWAVE_SOURCE_NODE_UNIQUE_ID

    assert ent_reg.async_is_registered(ZWAVE_BATTERY_ENTITY)
    battery_entry = ent_reg.async_get(ZWAVE_BATTERY_ENTITY)
    assert battery_entry.unique_id == ZWAVE_BATTERY_UNIQUE_ID

    assert ent_reg.async_is_registered(ZWAVE_POWER_ENTITY)
    power_entry = ent_reg.async_get(ZWAVE_POWER_ENTITY)
    assert power_entry.unique_id == ZWAVE_POWER_UNIQUE_ID

    # check that the zwave config entry has not been removed
    assert hass.config_entries.async_entries("zwave")

    # Check that the zwave integration can be setup after dry run
    zwave_config_entry = zwave_integration
    with patch("openzwave.option.ZWaveOption"), patch("openzwave.network.ZWaveNetwork"):
        assert await hass.config_entries.async_setup(zwave_config_entry.entry_id)


async def test_migrate_zwave_not_setup(hass, migration_data, hass_ws_client):
    """Test the zwave to ozw migration websocket without zwave setup."""
    await setup_ozw(hass, fixture=migration_data)
    client = await hass_ws_client(hass)

    await client.send_json({ID: 5, TYPE: "ozw/migrate_zwave"})
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "zwave_not_loaded"
    assert msg["error"]["message"] == "Integration zwave is not loaded"


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
