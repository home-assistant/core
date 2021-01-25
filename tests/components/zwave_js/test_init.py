"""Test the Z-Wave JS init module."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE

from .common import AIR_TEMPERATURE_SENSOR

from tests.common import MockConfigEntry


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture():
    """Mock the connect timeout."""
    with patch("homeassistant.components.zwave_js.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


async def test_entry_setup_unload(hass, client, integration):
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert client.register_on_initialized.call_count == 1
    assert client.register_on_disconnect.call_count == 1
    assert client.register_on_connect.call_count == 1
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert client.register_on_initialized.return_value.call_count == 1
    assert client.register_on_disconnect.return_value.call_count == 1
    assert client.register_on_connect.return_value.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_home_assistant_stop(hass, client, integration):
    """Test we clean up on home assistant stop."""
    await hass.async_stop()

    assert client.disconnect.call_count == 1


async def test_availability_reflect_connection_status(
    hass, client, multisensor_6, integration
):
    """Test we handle disconnect and reconnect."""
    on_initialized = client.register_on_initialized.call_args[0][0]
    on_disconnect = client.register_on_disconnect.call_args[0][0]
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state != STATE_UNAVAILABLE

    client.connected = False

    await on_disconnect()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == STATE_UNAVAILABLE

    client.connected = True

    await on_initialized()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state != STATE_UNAVAILABLE


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
