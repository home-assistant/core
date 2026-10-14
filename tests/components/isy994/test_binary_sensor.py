"""Test the ISY994 binary sensor platform."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyisy.constants import CMD_ON
from pyisy.helpers import EventEmitter, NodeProperty
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.isy994.binary_sensor import (
    ISYBinarySensorHeartbeat,
    ISYInsteonBinarySensorEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from . import entity_listeners

from tests.common import MockConfigEntry, async_fire_time_changed

LEAK_SENSOR_ENTITY_ID = "binary_sensor.leak_sensor"
HEARTBEAT_ENTITY_ID = "binary_sensor.leak_sensor_heartbeat"


@pytest.fixture(autouse=True)
def mock_binary_sensor_platform():
    """Mock the platforms to only include binary_sensor."""
    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.fixture
def leak_sensor_nodes(
    mock_isy: MagicMock, mock_node: Callable[..., Any]
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return the parent, negative and heartbeat nodes of an Insteon leak sensor."""
    parent = mock_node(mock_isy, "1A 2B 3C 1", "Leak Sensor", "BinaryAlarm", "16.8.1.0")
    children = [
        mock_node(mock_isy, address, name, "BinaryAlarm", "16.8.1.0")
        for address, name in (
            ("1A 2B 3C 2", "Leak Sensor Dry"),
            ("1A 2B 3C 4", "Leak Sensor Heartbeat"),
        )
    ]
    for node in (parent, *children):
        node.status_events = EventEmitter()
        node.control_events = EventEmitter()
    for child in children:
        child.parent_node = parent
        child.primary_node = parent.address
    mock_isy.nodes.status_events = EventEmitter()
    mock_isy.nodes.__iter__.return_value = [
        (node.name, node) for node in (parent, *children)
    ]
    return parent, children[0], children[1]


async def _async_setup_leak_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> tuple[ISYInsteonBinarySensorEntity, ISYBinarySensorHeartbeat]:
    """Set up the integration and return the leak sensor and heartbeat entities."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    component = hass.data[DATA_INSTANCES][BINARY_SENSOR_DOMAIN]
    parent = component.get_entity(LEAK_SENSOR_ENTITY_ID)
    heartbeat = component.get_entity(HEARTBEAT_ENTITY_ID)
    assert isinstance(parent, ISYInsteonBinarySensorEntity)
    assert isinstance(heartbeat, ISYBinarySensorHeartbeat)
    return parent, heartbeat


async def test_insteon_listeners_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    leak_sensor_nodes: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test removing an Insteon sensor unsubscribes its positive and negative nodes."""
    parent_node, negative_node, _ = leak_sensor_nodes
    parent, _ = await _async_setup_leak_sensor(hass, mock_config_entry)
    emitters = (
        parent_node.status_events,
        parent_node.control_events,
        negative_node.control_events,
    )
    # Control events feed both the base entity and the positive node handler.
    assert [len(entity_listeners(emitter, parent)) for emitter in emitters] == [
        1,
        2,
        1,
    ]

    entity_registry.async_remove(LEAK_SENSOR_ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(LEAK_SENSOR_ENTITY_ID) is None
    assert [emitter._subscribers for emitter in emitters] == [[], [], []]


async def test_heartbeat_attached_to_parent(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    leak_sensor_nodes: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test parent control events reset the heartbeat after it timed out."""
    parent_node, _, _ = leak_sensor_nodes
    parent, heartbeat = await _async_setup_leak_sensor(hass, mock_config_entry)
    assert parent._heartbeat_device is heartbeat

    freezer.tick(timedelta(hours=26))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(HEARTBEAT_ENTITY_ID).state == STATE_ON

    parent_node.control_events.notify(NodeProperty(CMD_ON))
    await hass.async_block_till_done()
    assert hass.states.get(HEARTBEAT_ENTITY_ID).state == STATE_OFF


async def test_heartbeat_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    leak_sensor_nodes: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test removing the heartbeat unsubscribes, detaches and stops its timer."""
    parent_node, _, heartbeat_node = leak_sensor_nodes
    parent, heartbeat = await _async_setup_leak_sensor(hass, mock_config_entry)
    emitters = (heartbeat_node.status_events, heartbeat_node.control_events)
    # Control events feed both the base entity and the heartbeat handler.
    assert [len(entity_listeners(emitter, heartbeat)) for emitter in emitters] == [
        1,
        2,
    ]
    assert heartbeat._heartbeat_timer is not None
    computed_state = heartbeat._computed_state

    entity_registry.async_remove(HEARTBEAT_ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(HEARTBEAT_ENTITY_ID) is None
    assert [emitter._subscribers for emitter in emitters] == [[], []]
    assert parent._heartbeat_device is None
    assert heartbeat._heartbeat_timer is None

    freezer.tick(timedelta(hours=26))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert heartbeat._computed_state is computed_state

    # Parent activity must not re-arm the removed heartbeat's timer.
    parent_node.control_events.notify(NodeProperty(CMD_ON))
    await hass.async_block_till_done()
    assert heartbeat._heartbeat_timer is None
    # The parent still handled the event; DON on a leak sensor means dry.
    assert hass.states.get(LEAK_SENSOR_ENTITY_ID).state == STATE_OFF


async def test_heartbeat_entity_id_change_keeps_attachment(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    leak_sensor_nodes: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test renaming the heartbeat entity keeps it attached and subscribed once."""
    _, _, heartbeat_node = leak_sensor_nodes
    parent, heartbeat = await _async_setup_leak_sensor(hass, mock_config_entry)
    new_entity_id = "binary_sensor.renamed_heartbeat"

    entity_registry.async_update_entity(
        HEARTBEAT_ENTITY_ID, new_entity_id=new_entity_id
    )
    await hass.async_block_till_done()

    assert hass.states.get(HEARTBEAT_ENTITY_ID) is None
    assert hass.states.get(new_entity_id) is not None
    assert heartbeat.entity_id == new_entity_id
    assert parent._heartbeat_device is heartbeat
    assert [
        listener.callback
        for listener in heartbeat_node.control_events._subscribers
        if listener.callback == heartbeat._heartbeat_node_control_handler
    ] == [heartbeat._heartbeat_node_control_handler]
