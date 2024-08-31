"""Test the Z-Wave JS migration module."""
import copy

import pytest
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import AIR_TEMPERATURE_SENSOR, NOTIFICATION_MOTION_BINARY_SENSOR


async def test_unique_id_migration_dupes(
    hass: HomeAssistant, multisensor_6_state, client, integration
) -> None:
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
        "52.52-49-00-Air temperature-00",
        "52.52-49-0-Air temperature-00-00",
        "52-49-0-Air temperature-00-00",
    ],
)
async def test_unique_id_migration(
    hass: HomeAssistant, multisensor_6_state, client, integration, id
) -> None:
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
        "32.32-50-00-value-W_Consumed",
        "32.32-50-0-value-66049-W_Consumed",
        "32-50-0-value-66049-W_Consumed",
    ],
)
async def test_unique_id_migration_property_key(
    hass: HomeAssistant, hank_binary_switch_state, client, integration, id
) -> None:
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
    hass: HomeAssistant, multisensor_6_state, client, integration
) -> None:
    """Test unique ID is migrated from old format to new for a notification binary sensor."""
    ent_reg = er.async_get(hass)

    entity_name = NOTIFICATION_MOTION_BINARY_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = (
        f"{client.driver.controller.home_id}.52.52-113-00-Home Security-Motion sensor"
        " status.8"
    )
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
    new_unique_id = (
        f"{client.driver.controller.home_id}.52-113-0-Home Security-Motion sensor"
        " status.8"
    )
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id("binary_sensor", DOMAIN, old_unique_id) is None


async def test_old_entity_migration(
    hass: HomeAssistant, hank_binary_switch_state, client, integration
) -> None:
    """Test old entity on a different endpoint is migrated to a new one."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    driver = client.driver
    assert driver

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(driver, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create entity RegistryEntry using fake endpoint
    old_unique_id = f"{driver.controller.home_id}.32-50-1-value-66049"
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
    for _ in range(2):
        # Add a ready node, unique ID should be migrated
        event = {"node": node}
        driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that new RegistryEntry is using new unique ID format
        entity_entry = ent_reg.async_get(SENSOR_NAME)
        new_unique_id = f"{client.driver.controller.home_id}.32-50-0-value-66049"
        assert entity_entry.unique_id == new_unique_id
        assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


async def test_different_endpoint_migration_status_sensor(
    hass: HomeAssistant, hank_binary_switch_state, client, integration
) -> None:
    """Test that the different endpoint migration logic skips over the status sensor."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    driver = client.driver
    assert driver

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(driver, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_status_sensor"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create entity RegistryEntry using fake endpoint
    old_unique_id = f"{driver.controller.home_id}.32.node_status"
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
    for _ in range(0, 2):
        # Add a ready node, unique ID should be migrated
        event = {"node": node}
        driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that the RegistryEntry is using the same unique ID
        entity_entry = ent_reg.async_get(SENSOR_NAME)
        assert entity_entry.unique_id == old_unique_id


async def test_skip_old_entity_migration_for_multiple(
    hass: HomeAssistant, hank_binary_switch_state, client, integration
) -> None:
    """Test that multiple entities of the same value but on a different endpoint get skipped."""
    node = Node(client, copy.deepcopy(hank_binary_switch_state))
    driver = client.driver
    assert driver

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(driver, node)},
        manufacturer=hank_binary_switch_state["deviceConfig"]["manufacturer"],
        model=hank_binary_switch_state["deviceConfig"]["label"],
    )

    SENSOR_NAME = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
    entity_name = SENSOR_NAME.split(".")[1]

    # Create two entity entrrys using different endpoints
    old_unique_id_1 = f"{driver.controller.home_id}.32-50-1-value-66049"
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
    old_unique_id_2 = f"{driver.controller.home_id}.32-50-2-value-66049"
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
    driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is created using new unique ID format
    entity_entry = ent_reg.async_get(SENSOR_NAME)
    new_unique_id = f"{driver.controller.home_id}.32-50-0-value-66049"
    assert entity_entry.unique_id == new_unique_id

    # Check that the old entities stuck around because we skipped the migration step
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_1)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id_2)


async def test_old_entity_migration_notification_binary_sensor(
    hass: HomeAssistant, multisensor_6_state, client, integration
) -> None:
    """Test old entity on a different endpoint is migrated to a new one for a notification binary sensor."""
    node = Node(client, copy.deepcopy(multisensor_6_state))
    driver = client.driver
    assert driver

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={get_device_id(driver, node)},
        manufacturer=multisensor_6_state["deviceConfig"]["manufacturer"],
        model=multisensor_6_state["deviceConfig"]["label"],
    )

    entity_name = NOTIFICATION_MOTION_BINARY_SENSOR.split(".")[1]

    # Create entity RegistryEntry using old unique ID format
    old_unique_id = (
        f"{driver.controller.home_id}.52-113-1-Home Security-Motion sensor status.8"
    )
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
        driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        # Check that new RegistryEntry is using new unique ID format
        entity_entry = ent_reg.async_get(NOTIFICATION_MOTION_BINARY_SENSOR)
        new_unique_id = (
            f"{driver.controller.home_id}.52-113-0-Home Security-Motion sensor status.8"
        )
        assert entity_entry.unique_id == new_unique_id
        assert (
            ent_reg.async_get_entity_id("binary_sensor", DOMAIN, old_unique_id) is None
        )
