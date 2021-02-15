"""Test the Z-Wave JS init module."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from zwave_js_server.model.node import Node

from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.entity import get_device_id
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry, entity_registry

from .common import AIR_TEMPERATURE_SENSOR

from tests.common import MockConfigEntry


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture():
    """Mock the connect timeout."""
    with patch("homeassistant.components.zwave_js.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


@pytest.fixture(name="stop_addon")
def stop_addon_fixture():
    """Mock stop add-on."""
    with patch("homeassistant.components.hassio.async_stop_addon") as stop_addon:
        yield stop_addon


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture():
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


async def test_entry_setup_unload(hass, client, integration):
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_home_assistant_stop(hass, client, integration):
    """Test we clean up on home assistant stop."""
    await hass.async_stop()

    assert client.disconnect.call_count == 1


async def test_initialized_timeout(hass, client, connect_timeout):
    """Test we handle a timeout during client initialization."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_on_node_added_ready(
    hass, multisensor_6_state, client, integration, device_registry
):
    """Test we handle a ready node added event."""
    node = Node(client, multisensor_6_state)
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )


async def test_on_node_added_not_ready(
    hass, multisensor_6_state, client, integration, device_registry
):
    """Test we handle a non ready node added event."""
    node_data = deepcopy(multisensor_6_state)  # Copy to allow modification in tests.
    node = Node(client, node_data)
    node.data["ready"] = False
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity not yet added but device added in registry
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    node.data["ready"] = True
    node.emit("ready", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity added
    assert state.state != STATE_UNAVAILABLE


async def test_existing_node_ready(
    hass, client, multisensor_6, integration, device_registry
):
    """Test we handle a ready node that exists during integration setup."""
    node = multisensor_6
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )


async def test_existing_node_not_ready(hass, client, multisensor_6, device_registry):
    """Test we handle a non ready node that exists during integration setup."""
    node = multisensor_6
    node.data = deepcopy(node.data)  # Copy to allow modification in tests.
    node.data["ready"] = False
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity not yet added
    assert device_registry.async_get_device(  # device should be added
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    node.data["ready"] = True
    node.emit("ready", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )


async def test_remove_entry(hass, stop_addon, uninstall_addon, caplog):
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        connection_class=CONN_CLASS_LOCAL_PUSH,
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        connection_class=CONN_CLASS_LOCAL_PUSH,
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert uninstall_addon.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert uninstall_addon.call_count == 0
    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the Z-Wave JS add-on" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert uninstall_addon.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Z-Wave JS add-on" in caplog.text


async def test_removed_device(hass, client, multiple_devices, integration):
    """Test that the device registry gets updated when a device gets removed."""
    nodes = multiple_devices

    # Verify how many nodes are available
    assert len(client.driver.controller.nodes) == 2

    # Make sure there are the same number of devices
    dev_reg = await device_registry.async_get_registry(hass)
    device_entries = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )
    assert len(device_entries) == 2

    # Check how many entities there are
    ent_reg = await entity_registry.async_get_registry(hass)
    entity_entries = entity_registry.async_entries_for_config_entry(
        ent_reg, integration.entry_id
    )
    assert len(entity_entries) == 24

    # Remove a node and reload the entry
    old_node = nodes.pop(13)
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Assert that the node and all of it's entities were removed from the device and
    # entity registry
    device_entries = device_registry.async_entries_for_config_entry(
        dev_reg, integration.entry_id
    )
    assert len(device_entries) == 1
    entity_entries = entity_registry.async_entries_for_config_entry(
        ent_reg, integration.entry_id
    )
    assert len(entity_entries) == 15
    assert dev_reg.async_get_device({get_device_id(client, old_node)}) is None
