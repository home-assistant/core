"""Test zwave to ozw migration."""
from unittest.mock import patch

import pytest

from homeassistant.components.ozw.websocket_api import ID, TYPE
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import setup_ozw

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
ZWAVE_POWER_ENTITY = "binary_sensor.zwave_power"
ZWAVE_POWER_UNIQUE_ID = "32-5678"
ZWAVE_POWER_NAME = "Z-Wave Power"
ZWAVE_POWER_ICON = "mdi:zwave-test-power"


@pytest.fixture(name="zwave_migration_data")
def zwave_migration_data_fixture(hass):
    """Return mock zwave migration data."""
    zwave_source_node_device = dr.DeviceEntry(
        id=ZWAVE_SOURCE_NODE_DEVICE_ID,
        name_by_user=ZWAVE_SOURCE_NODE_DEVICE_NAME,
        area_id=ZWAVE_SOURCE_NODE_DEVICE_AREA,
    )
    zwave_source_node_entry = er.RegistryEntry(
        entity_id=ZWAVE_SOURCE_ENTITY,
        unique_id=ZWAVE_SOURCE_NODE_UNIQUE_ID,
        platform="zwave",
        name="Z-Wave Source Node",
    )
    zwave_battery_device = dr.DeviceEntry(
        id=ZWAVE_BATTERY_DEVICE_ID,
        name_by_user=ZWAVE_BATTERY_DEVICE_NAME,
        area_id=ZWAVE_BATTERY_DEVICE_AREA,
    )
    zwave_battery_entry = er.RegistryEntry(
        entity_id=ZWAVE_BATTERY_ENTITY,
        unique_id=ZWAVE_BATTERY_UNIQUE_ID,
        platform="zwave",
        name=ZWAVE_BATTERY_NAME,
        icon=ZWAVE_BATTERY_ICON,
    )
    zwave_power_device = dr.DeviceEntry(
        id=ZWAVE_POWER_DEVICE_ID,
        name_by_user=ZWAVE_POWER_DEVICE_NAME,
        area_id=ZWAVE_POWER_DEVICE_AREA,
    )
    zwave_power_entry = er.RegistryEntry(
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

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

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

    # this should have been migrated and no longer present under that id
    assert not ent_reg.async_is_registered("sensor.water_sensor_6_battery_level")

    # these should not have been migrated and is still in the registry
    assert ent_reg.async_is_registered(ZWAVE_SOURCE_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_SOURCE_ENTITY)
    assert source_entry.unique_id == ZWAVE_SOURCE_NODE_UNIQUE_ID
    assert ent_reg.async_is_registered(ZWAVE_POWER_ENTITY)
    source_entry = ent_reg.async_get(ZWAVE_POWER_ENTITY)
    assert source_entry.unique_id == ZWAVE_POWER_UNIQUE_ID
    assert ent_reg.async_is_registered("sensor.smart_plug_electric_w")

    # this is the new entity_id of the ozw entity
    assert ent_reg.async_is_registered(ZWAVE_BATTERY_ENTITY)

    # check that the migrated entries have correct attributes
    battery_entry = ent_reg.async_get(ZWAVE_BATTERY_ENTITY)
    assert battery_entry.unique_id == "1-36-610271249"
    assert battery_entry.name == ZWAVE_BATTERY_NAME
    assert battery_entry.icon == ZWAVE_BATTERY_ICON

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

    ent_reg = er.async_get(hass)

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
