"""Test the Z-Wave JS migration module."""
import copy
from unittest.mock import patch

import pytest
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.api import ENTRY_ID, ID, TYPE
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.const import LIGHT_LUX
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import AIR_TEMPERATURE_SENSOR, NOTIFICATION_MOTION_BINARY_SENSOR

from tests.common import MockConfigEntry, mock_device_registry, mock_registry

# Switch device
ZWAVE_SWITCH_DEVICE_ID = "zwave_switch_device_id"
ZWAVE_SWITCH_DEVICE_NAME = "Z-Wave Switch Device"
ZWAVE_SWITCH_DEVICE_AREA = "Z-Wave Switch Area"
ZWAVE_SWITCH_ENTITY = "switch.zwave_switch_node"
ZWAVE_SWITCH_UNIQUE_ID = "102-6789"
ZWAVE_SWITCH_NAME = "Z-Wave Switch"
ZWAVE_SWITCH_ICON = "mdi:zwave-test-switch"
ZWAVE_POWER_ENTITY = "sensor.zwave_power"
ZWAVE_POWER_UNIQUE_ID = "102-5678"
ZWAVE_POWER_NAME = "Z-Wave Power"
ZWAVE_POWER_ICON = "mdi:zwave-test-power"

# Multisensor device
ZWAVE_MULTISENSOR_DEVICE_ID = "zwave_multisensor_device_id"
ZWAVE_MULTISENSOR_DEVICE_NAME = "Z-Wave Multisensor Device"
ZWAVE_MULTISENSOR_DEVICE_AREA = "Z-Wave Multisensor Area"
ZWAVE_SOURCE_NODE_ENTITY = "sensor.zwave_source_node"
ZWAVE_SOURCE_NODE_UNIQUE_ID = "52-4321"
ZWAVE_LUMINANCE_ENTITY = "sensor.zwave_luminance"
ZWAVE_LUMINANCE_UNIQUE_ID = "52-6543"
ZWAVE_LUMINANCE_NAME = "Z-Wave Luminance"
ZWAVE_LUMINANCE_ICON = "mdi:zwave-test-luminance"
ZWAVE_BATTERY_ENTITY = "sensor.zwave_battery_level"
ZWAVE_BATTERY_UNIQUE_ID = "52-1234"
ZWAVE_BATTERY_NAME = "Z-Wave Battery Level"
ZWAVE_BATTERY_ICON = "mdi:zwave-test-battery"
ZWAVE_TAMPERING_ENTITY = "sensor.zwave_tampering"
ZWAVE_TAMPERING_UNIQUE_ID = "52-3456"
ZWAVE_TAMPERING_NAME = "Z-Wave Tampering"
ZWAVE_TAMPERING_ICON = "mdi:zwave-test-tampering"


@pytest.fixture(name="zwave_migration_data")
def zwave_migration_data_fixture(hass):
    """Return mock zwave migration data."""
    zwave_switch_device = dr.DeviceEntry(
        id=ZWAVE_SWITCH_DEVICE_ID,
        name_by_user=ZWAVE_SWITCH_DEVICE_NAME,
        area_id=ZWAVE_SWITCH_DEVICE_AREA,
    )
    zwave_switch_entry = er.RegistryEntry(
        entity_id=ZWAVE_SWITCH_ENTITY,
        unique_id=ZWAVE_SWITCH_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_SWITCH_NAME,
        icon=ZWAVE_SWITCH_ICON,
    )
    zwave_multisensor_device = dr.DeviceEntry(
        id=ZWAVE_MULTISENSOR_DEVICE_ID,
        name_by_user=ZWAVE_MULTISENSOR_DEVICE_NAME,
        area_id=ZWAVE_MULTISENSOR_DEVICE_AREA,
    )
    zwave_source_node_entry = er.RegistryEntry(
        entity_id=ZWAVE_SOURCE_NODE_ENTITY,
        unique_id=ZWAVE_SOURCE_NODE_UNIQUE_ID,
        platform="zwave",
        name="Z-Wave Source Node",
    )
    zwave_luminance_entry = er.RegistryEntry(
        entity_id=ZWAVE_LUMINANCE_ENTITY,
        unique_id=ZWAVE_LUMINANCE_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_LUMINANCE_NAME,
        icon=ZWAVE_LUMINANCE_ICON,
        unit_of_measurement="lux",
    )
    zwave_battery_entry = er.RegistryEntry(
        entity_id=ZWAVE_BATTERY_ENTITY,
        unique_id=ZWAVE_BATTERY_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_BATTERY_NAME,
        icon=ZWAVE_BATTERY_ICON,
        unit_of_measurement="%",
    )
    zwave_power_entry = er.RegistryEntry(
        entity_id=ZWAVE_POWER_ENTITY,
        unique_id=ZWAVE_POWER_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_POWER_NAME,
        icon=ZWAVE_POWER_ICON,
        unit_of_measurement="W",
    )
    zwave_tampering_entry = er.RegistryEntry(
        entity_id=ZWAVE_TAMPERING_ENTITY,
        unique_id=ZWAVE_TAMPERING_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_TAMPERING_NAME,
        icon=ZWAVE_TAMPERING_ICON,
        unit_of_measurement="",  # Test empty string unit normalization.
    )

    zwave_migration_data = {
        ZWAVE_SWITCH_ENTITY: {
            "node_id": 102,
            "node_instance": 1,
            "command_class": 37,
            "command_class_label": "",
            "value_index": 1,
            "device_id": zwave_switch_device.id,
            "domain": zwave_switch_entry.domain,
            "entity_id": zwave_switch_entry.entity_id,
            "unique_id": ZWAVE_SWITCH_UNIQUE_ID,
            "unit_of_measurement": zwave_switch_entry.unit_of_measurement,
        },
        ZWAVE_POWER_ENTITY: {
            "node_id": 102,
            "node_instance": 1,
            "command_class": 50,
            "command_class_label": "Power",
            "value_index": 8,
            "device_id": zwave_switch_device.id,
            "domain": zwave_power_entry.domain,
            "entity_id": zwave_power_entry.entity_id,
            "unique_id": ZWAVE_POWER_UNIQUE_ID,
            "unit_of_measurement": zwave_power_entry.unit_of_measurement,
        },
        ZWAVE_SOURCE_NODE_ENTITY: {
            "node_id": 52,
            "node_instance": 1,
            "command_class": 113,
            "command_class_label": "SourceNodeId",
            "value_index": 1,
            "device_id": zwave_multisensor_device.id,
            "domain": zwave_source_node_entry.domain,
            "entity_id": zwave_source_node_entry.entity_id,
            "unique_id": ZWAVE_SOURCE_NODE_UNIQUE_ID,
            "unit_of_measurement": zwave_source_node_entry.unit_of_measurement,
        },
        ZWAVE_LUMINANCE_ENTITY: {
            "node_id": 52,
            "node_instance": 1,
            "command_class": 49,
            "command_class_label": "Luminance",
            "value_index": 3,
            "device_id": zwave_multisensor_device.id,
            "domain": zwave_luminance_entry.domain,
            "entity_id": zwave_luminance_entry.entity_id,
            "unique_id": ZWAVE_LUMINANCE_UNIQUE_ID,
            "unit_of_measurement": zwave_luminance_entry.unit_of_measurement,
        },
        ZWAVE_BATTERY_ENTITY: {
            "node_id": 52,
            "node_instance": 1,
            "command_class": 128,
            "command_class_label": "Battery Level",
            "value_index": 0,
            "device_id": zwave_multisensor_device.id,
            "domain": zwave_battery_entry.domain,
            "entity_id": zwave_battery_entry.entity_id,
            "unique_id": ZWAVE_BATTERY_UNIQUE_ID,
            "unit_of_measurement": zwave_battery_entry.unit_of_measurement,
        },
        ZWAVE_TAMPERING_ENTITY: {
            "node_id": 52,
            "node_instance": 1,
            "command_class": 113,
            "command_class_label": "Burglar",
            "value_index": 10,
            "device_id": zwave_multisensor_device.id,
            "domain": zwave_tampering_entry.domain,
            "entity_id": zwave_tampering_entry.entity_id,
            "unique_id": ZWAVE_TAMPERING_UNIQUE_ID,
            "unit_of_measurement": zwave_tampering_entry.unit_of_measurement,
        },
    }

    mock_device_registry(
        hass,
        {
            zwave_switch_device.id: zwave_switch_device,
            zwave_multisensor_device.id: zwave_multisensor_device,
        },
    )
    mock_registry(
        hass,
        {
            ZWAVE_SWITCH_ENTITY: zwave_switch_entry,
            ZWAVE_SOURCE_NODE_ENTITY: zwave_source_node_entry,
            ZWAVE_LUMINANCE_ENTITY: zwave_luminance_entry,
            ZWAVE_BATTERY_ENTITY: zwave_battery_entry,
            ZWAVE_POWER_ENTITY: zwave_power_entry,
            ZWAVE_TAMPERING_ENTITY: zwave_tampering_entry,
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
        "homeassistant.components.zwave.async_get_migration_data",
        return_value=zwave_migration_data,
    ):
        yield zwave_config_entry


@pytest.mark.skip(reason="The old zwave integration has been removed.")
async def test_migrate_zwave(
    hass,
    zwave_integration,
    aeon_smart_switch_6,
    multisensor_6,
    integration,
    hass_ws_client,
):
    """Test the Z-Wave to Z-Wave JS migration websocket api."""
    entry = integration
    client = await hass_ws_client(hass)

    assert hass.config_entries.async_entries("zwave")

    await client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/migrate_zwave",
            ENTRY_ID: entry.entry_id,
            "dry_run": False,
        }
    )
    msg = await client.receive_json()
    result = msg["result"]

    migration_entity_map = {
        ZWAVE_SWITCH_ENTITY: "switch.smart_switch_6",
        ZWAVE_LUMINANCE_ENTITY: "sensor.multisensor_6_illuminance",
        ZWAVE_BATTERY_ENTITY: "sensor.multisensor_6_battery_level",
    }

    assert result["zwave_entity_ids"] == [
        ZWAVE_SWITCH_ENTITY,
        ZWAVE_POWER_ENTITY,
        ZWAVE_SOURCE_NODE_ENTITY,
        ZWAVE_LUMINANCE_ENTITY,
        ZWAVE_BATTERY_ENTITY,
        ZWAVE_TAMPERING_ENTITY,
    ]
    expected_zwave_js_entities = [
        "switch.smart_switch_6",
        "sensor.multisensor_6_air_temperature",
        "sensor.multisensor_6_illuminance",
        "sensor.multisensor_6_humidity",
        "sensor.multisensor_6_ultraviolet",
        "binary_sensor.multisensor_6_home_security_tampering_product_cover_removed",
        "binary_sensor.multisensor_6_home_security_motion_detection",
        "sensor.multisensor_6_battery_level",
        "binary_sensor.multisensor_6_low_battery_level",
        "light.smart_switch_6",
        "sensor.smart_switch_6_electric_consumed_kwh",
        "sensor.smart_switch_6_electric_consumed_w",
        "sensor.smart_switch_6_electric_consumed_v",
        "sensor.smart_switch_6_electric_consumed_a",
    ]
    # Assert that both lists have the same items without checking order
    assert not set(result["zwave_js_entity_ids"]) ^ set(expected_zwave_js_entities)
    assert result["migration_entity_map"] == migration_entity_map
    assert result["migrated"] is True

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # check the device registry migration

    # check that the migrated entries have correct attributes
    multisensor_device_entry = dev_reg.async_get_device(
        identifiers={("zwave_js", "3245146787-52")}, connections=set()
    )
    assert multisensor_device_entry
    assert multisensor_device_entry.name_by_user == ZWAVE_MULTISENSOR_DEVICE_NAME
    assert multisensor_device_entry.area_id == ZWAVE_MULTISENSOR_DEVICE_AREA
    switch_device_entry = dev_reg.async_get_device(
        identifiers={("zwave_js", "3245146787-102")}, connections=set()
    )
    assert switch_device_entry
    assert switch_device_entry.name_by_user == ZWAVE_SWITCH_DEVICE_NAME
    assert switch_device_entry.area_id == ZWAVE_SWITCH_DEVICE_AREA

    migration_device_map = {
        ZWAVE_SWITCH_DEVICE_ID: switch_device_entry.id,
        ZWAVE_MULTISENSOR_DEVICE_ID: multisensor_device_entry.id,
    }

    assert result["migration_device_map"] == migration_device_map

    # check the entity registry migration

    # this should have been migrated and no longer present under that id
    assert not ent_reg.async_is_registered("sensor.multisensor_6_battery_level")
    assert not ent_reg.async_is_registered("sensor.multisensor_6_illuminance")

    # these should not have been migrated and is still in the registry
    assert ent_reg.async_is_registered(ZWAVE_SOURCE_NODE_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_SOURCE_NODE_ENTITY)
    assert source_entry.unique_id == ZWAVE_SOURCE_NODE_UNIQUE_ID
    assert ent_reg.async_is_registered(ZWAVE_POWER_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_POWER_ENTITY)
    assert source_entry.unique_id == ZWAVE_POWER_UNIQUE_ID
    assert ent_reg.async_is_registered(ZWAVE_TAMPERING_ENTITY)
    tampering_entry = ent_reg.async_get(ZWAVE_TAMPERING_ENTITY)
    assert tampering_entry.unique_id == ZWAVE_TAMPERING_UNIQUE_ID
    assert ent_reg.async_is_registered("sensor.smart_switch_6_electric_consumed_w")

    # this is the new entity_ids of the zwave_js entities
    assert ent_reg.async_is_registered(ZWAVE_SWITCH_ENTITY)
    assert ent_reg.async_is_registered(ZWAVE_BATTERY_ENTITY)
    assert ent_reg.async_is_registered(ZWAVE_LUMINANCE_ENTITY)

    # check that the migrated entries have correct attributes
    switch_entry = ent_reg.async_get(ZWAVE_SWITCH_ENTITY)
    assert switch_entry
    assert switch_entry.unique_id == "3245146787.102-37-0-currentValue"
    assert switch_entry.name == ZWAVE_SWITCH_NAME
    assert switch_entry.icon == ZWAVE_SWITCH_ICON
    battery_entry = ent_reg.async_get(ZWAVE_BATTERY_ENTITY)
    assert battery_entry
    assert battery_entry.unique_id == "3245146787.52-128-0-level"
    assert battery_entry.name == ZWAVE_BATTERY_NAME
    assert battery_entry.icon == ZWAVE_BATTERY_ICON
    luminance_entry = ent_reg.async_get(ZWAVE_LUMINANCE_ENTITY)
    assert luminance_entry
    assert luminance_entry.unique_id == "3245146787.52-49-0-Illuminance"
    assert luminance_entry.name == ZWAVE_LUMINANCE_NAME
    assert luminance_entry.icon == ZWAVE_LUMINANCE_ICON
    assert luminance_entry.unit_of_measurement == LIGHT_LUX

    # check that the zwave config entry has been removed
    assert not hass.config_entries.async_entries("zwave")

    # Check that the zwave integration fails entry setup after migration
    zwave_config_entry = MockConfigEntry(domain="zwave")
    zwave_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(zwave_config_entry.entry_id)


@pytest.mark.skip(reason="The old zwave integration has been removed.")
async def test_migrate_zwave_dry_run(
    hass,
    zwave_integration,
    aeon_smart_switch_6,
    multisensor_6,
    integration,
    hass_ws_client,
):
    """Test the zwave to zwave_js migration websocket api dry run."""
    entry = integration
    client = await hass_ws_client(hass)

    await client.send_json(
        {ID: 5, TYPE: "zwave_js/migrate_zwave", ENTRY_ID: entry.entry_id}
    )
    msg = await client.receive_json()
    result = msg["result"]

    migration_entity_map = {
        ZWAVE_SWITCH_ENTITY: "switch.smart_switch_6",
        ZWAVE_BATTERY_ENTITY: "sensor.multisensor_6_battery_level",
    }

    assert result["zwave_entity_ids"] == [
        ZWAVE_SWITCH_ENTITY,
        ZWAVE_POWER_ENTITY,
        ZWAVE_SOURCE_NODE_ENTITY,
        ZWAVE_BATTERY_ENTITY,
        ZWAVE_TAMPERING_ENTITY,
    ]
    expected_zwave_js_entities = [
        "switch.smart_switch_6",
        "sensor.multisensor_6_air_temperature",
        "sensor.multisensor_6_illuminance",
        "sensor.multisensor_6_humidity",
        "sensor.multisensor_6_ultraviolet",
        "binary_sensor.multisensor_6_home_security_tampering_product_cover_removed",
        "binary_sensor.multisensor_6_home_security_motion_detection",
        "sensor.multisensor_6_battery_level",
        "binary_sensor.multisensor_6_low_battery_level",
        "light.smart_switch_6",
        "sensor.smart_switch_6_electric_consumed_kwh",
        "sensor.smart_switch_6_electric_consumed_w",
        "sensor.smart_switch_6_electric_consumed_v",
        "sensor.smart_switch_6_electric_consumed_a",
    ]
    # Assert that both lists have the same items without checking order
    assert not set(result["zwave_js_entity_ids"]) ^ set(expected_zwave_js_entities)
    assert result["migration_entity_map"] == migration_entity_map

    dev_reg = dr.async_get(hass)

    multisensor_device_entry = dev_reg.async_get_device(
        identifiers={("zwave_js", "3245146787-52")}, connections=set()
    )
    assert multisensor_device_entry
    assert multisensor_device_entry.name_by_user is None
    assert multisensor_device_entry.area_id is None
    switch_device_entry = dev_reg.async_get_device(
        identifiers={("zwave_js", "3245146787-102")}, connections=set()
    )
    assert switch_device_entry
    assert switch_device_entry.name_by_user is None
    assert switch_device_entry.area_id is None

    migration_device_map = {
        ZWAVE_SWITCH_DEVICE_ID: switch_device_entry.id,
        ZWAVE_MULTISENSOR_DEVICE_ID: multisensor_device_entry.id,
    }

    assert result["migration_device_map"] == migration_device_map

    assert result["migrated"] is False

    ent_reg = er.async_get(hass)

    # no real migration should have been done
    assert ent_reg.async_is_registered("switch.smart_switch_6")
    assert ent_reg.async_is_registered("sensor.multisensor_6_battery_level")
    assert ent_reg.async_is_registered("sensor.smart_switch_6_electric_consumed_w")

    assert ent_reg.async_is_registered(ZWAVE_SOURCE_NODE_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_SOURCE_NODE_ENTITY)
    assert source_entry
    assert source_entry.unique_id == ZWAVE_SOURCE_NODE_UNIQUE_ID

    assert ent_reg.async_is_registered(ZWAVE_BATTERY_ENTITY)
    battery_entry = ent_reg.async_get(ZWAVE_BATTERY_ENTITY)
    assert battery_entry
    assert battery_entry.unique_id == ZWAVE_BATTERY_UNIQUE_ID

    assert ent_reg.async_is_registered(ZWAVE_POWER_ENTITY)
    power_entry = ent_reg.async_get(ZWAVE_POWER_ENTITY)
    assert power_entry
    assert power_entry.unique_id == ZWAVE_POWER_UNIQUE_ID

    # check that the zwave config entry has not been removed
    assert hass.config_entries.async_entries("zwave")

    # Check that the zwave integration can be setup after dry run
    zwave_config_entry = zwave_integration
    with patch("openzwave.option.ZWaveOption"), patch("openzwave.network.ZWaveNetwork"):
        assert await hass.config_entries.async_setup(zwave_config_entry.entry_id)


async def test_migrate_zwave_not_setup(
    hass, aeon_smart_switch_6, multisensor_6, integration, hass_ws_client
):
    """Test the zwave to zwave_js migration websocket without zwave setup."""
    entry = integration
    client = await hass_ws_client(hass)

    await client.send_json(
        {ID: 5, TYPE: "zwave_js/migrate_zwave", ENTRY_ID: entry.entry_id}
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "zwave_not_loaded"
    assert msg["error"]["message"] == "Integration zwave is not loaded"


async def test_unique_id_migration_dupes(
    hass, multisensor_6_state, client, integration
):
    """Test we remove an entity when ."""
    ent_reg = er.async_get(hass)

    entity_name = AIR_TEMPERATURE_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id_1 = (
        f"{client.driver.controller.home_id}.52.52-49-00-Air temperature-00"
    )
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id_1,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == AIR_TEMPERATURE_SENSOR
    assert entity_entry.unique_id == old_unique_id_1

    # Create entity RegistryEntry using b0 unique ID format
    old_unique_id_2 = (
        f"{client.driver.controller.home_id}.52.52-49-0-Air temperature-00-00"
    )
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id_2,
        suggested_object_id=f"{entity_name}_1",
        config_entry=integration,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == f"{AIR_TEMPERATURE_SENSOR}_1"
    assert entity_entry.unique_id == old_unique_id_2

    # Add a ready node, unique ID should be migrated
    node = Node(client, copy.deepcopy(multisensor_6_state))
    event = {"node": node}

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(AIR_TEMPERATURE_SENSOR)
    new_unique_id = f"{client.driver.controller.home_id}.52-49-0-Air temperature"
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_1) is None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_2) is None


@pytest.mark.parametrize(
    "id",
    [
        ("52.52-49-00-Air temperature-00"),
        ("52.52-49-0-Air temperature-00-00"),
        ("52-49-0-Air temperature-00-00"),
    ],
)
async def test_unique_id_migration(hass, multisensor_6_state, client, integration, id):
    """Test unique ID is migrated from old format to new."""
    ent_reg = er.async_get(hass)

    # Migrate version 1
    entity_name = AIR_TEMPERATURE_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = f"{client.driver.controller.home_id}.{id}"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == AIR_TEMPERATURE_SENSOR
    assert entity_entry.unique_id == old_unique_id

    # Add a ready node, unique ID should be migrated
    node = Node(client, copy.deepcopy(multisensor_6_state))
    event = {"node": node}

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(AIR_TEMPERATURE_SENSOR)
    new_unique_id = f"{client.driver.controller.home_id}.52-49-0-Air temperature"
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


@pytest.mark.parametrize(
    "id",
    [
        ("32.32-50-00-value-W_Consumed"),
        ("32.32-50-0-value-66049-W_Consumed"),
        ("32-50-0-value-66049-W_Consumed"),
    ],
)
async def test_unique_id_migration_property_key(
    hass, hank_binary_switch_state, client, integration, id
):
    """Test unique ID with property key is migrated from old format to new."""
    ent_reg = er.async_get(hass)

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = f"{client.driver.controller.home_id}.{id}"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == SENSOR_NAME
    assert entity_entry.unique_id == old_unique_id

    # Add a ready node, unique ID should be migrated
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    event = {"node": node}

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(SENSOR_NAME)
    new_unique_id = f"{client.driver.controller.home_id}.32-50-0-value-66049"
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


async def test_unique_id_migration_notification_binary_sensor(
    hass, multisensor_6_state, client, integration
):
    """Test unique ID is migrated from old format to new for a notification binary sensor."""
    ent_reg = er.async_get(hass)

    entity_name = NOTIFICATION_MOTION_BINARY_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = f"{client.driver.controller.home_id}.52.52-113-00-Home Security-Motion sensor status.8"
    entity_entry = ent_reg.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == NOTIFICATION_MOTION_BINARY_SENSOR
    assert entity_entry.unique_id == old_unique_id

    # Add a ready node, unique ID should be migrated
    node = Node(client, copy.deepcopy(multisensor_6_state))
    event = {"node": node}

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(NOTIFICATION_MOTION_BINARY_SENSOR)
    new_unique_id = f"{client.driver.controller.home_id}.52-113-0-Home Security-Motion sensor status.8"
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("binary_sensor", DOMAIN, old_unique_id) is None


async def test_old_entity_migration(
    hass, hank_binary_switch_state, client, integration
):
    """Test old entity on a different endpoint is migrated to a new one."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(client, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create entity RegistryEntry using fake endpoint
    old_unique_id = f"{client.driver.controller.home_id}.32-50-1-value-66049"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
        device_id=device.id,
    )
    assert entity_entry.entity_id == SENSOR_NAME
    assert entity_entry.unique_id == old_unique_id

    # Do this twice to make sure re-interview doesn't do anything weird
    for i in range(0, 2):
        # Add a ready node, unique ID should be migrated
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that new RegistryEntry is using new unique ID format
        entity_entry = ent_reg.async_get(SENSOR_NAME)
        new_unique_id = f"{client.driver.controller.home_id}.32-50-0-value-66049"
        assert entity_entry.unique_id == new_unique_id
        assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


async def test_different_endpoint_migration_status_sensor(
    hass, hank_binary_switch_state, client, integration
):
    """Test that the different endpoint migration logic skips over the status sensor."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(client, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_status_sensor"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create entity RegistryEntry using fake endpoint
    old_unique_id = f"{client.driver.controller.home_id}.32.node_status"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
        device_id=device.id,
    )
    assert entity_entry.entity_id == SENSOR_NAME
    assert entity_entry.unique_id == old_unique_id

    # Do this twice to make sure re-interview doesn't do anything weird
    for i in range(0, 2):
        # Add a ready node, unique ID should be migrated
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that the RegistryEntry is using the same unique ID
        entity_entry = ent_reg.async_get(SENSOR_NAME)
        assert entity_entry.unique_id == old_unique_id


async def test_skip_old_entity_migration_for_multiple(
    hass, hank_binary_switch_state, client, integration
):
    """Test that multiple entities of the same value but on a different endpoint get skipped."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(client, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create two entity entrrys using different endpoints
    old_unique_id_1 = f"{client.driver.controller.home_id}.32-50-1-value-66049"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id_1,
        suggested_object_id=f"{entity_name}_1",
        config_entry=integration,
        original_name=f"{entity_name}_1",
        device_id=device.id,
    )
    assert entity_entry.entity_id == f"{SENSOR_NAME}_1"
    assert entity_entry.unique_id == old_unique_id_1

    # Create two entity entrrys using different endpoints
    old_unique_id_2 = f"{client.driver.controller.home_id}.32-50-2-value-66049"
    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id_2,
        suggested_object_id=f"{entity_name}_2",
        config_entry=integration,
        original_name=f"{entity_name}_2",
        device_id=device.id,
    )
    assert entity_entry.entity_id == f"{SENSOR_NAME}_2"
    assert entity_entry.unique_id == old_unique_id_2
    # Add a ready node, unique ID should be migrated
    event = {"node": node}
    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is created using new unique ID format
    entity_entry = ent_reg.async_get(SENSOR_NAME)
    new_unique_id = f"{client.driver.controller.home_id}.32-50-0-value-66049"
    assert entity_entry.unique_id == new_unique_id

    # Check that the old entities stuck around because we skipped the migration step
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_1)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_2)


async def test_old_entity_migration_notification_binary_sensor(
    hass, multisensor_6_state, client, integration
):
    """Test old entity on a different endpoint is migrated to a new one for a notification binary sensor."""
    node = Node(client, copy.deepcopy(multisensor_6_state))

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(client, node)},
        manufacturer=multisensor_6_state["deviceConfig"]["manufacturer"],
        model=multisensor_6_state["deviceConfig"]["label"],
    )

    entity_name = NOTIFICATION_MOTION_BINARY_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = f"{client.driver.controller.home_id}.52-113-1-Home Security-Motion sensor status.8"
    entity_entry = ent_reg.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=integration,
        original_name=entity_name,
        device_id=device.id,
    )
    assert entity_entry.entity_id == NOTIFICATION_MOTION_BINARY_SENSOR
    assert entity_entry.unique_id == old_unique_id

    # Do this twice to make sure re-interview doesn't do anything weird
    for _ in range(0, 2):
        # Add a ready node, unique ID should be migrated
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that new RegistryEntry is using new unique ID format
        entity_entry = ent_reg.async_get(NOTIFICATION_MOTION_BINARY_SENSOR)
        new_unique_id = f"{client.driver.controller.home_id}.52-113-0-Home Security-Motion sensor status.8"
        assert entity_entry.unique_id == new_unique_id
        assert (
            ent_reg.async_get_entity_id("binary_sensor", DOMAIN, old_unique_id) is None
        )
