"""Test Matter binary sensors."""

from unittest.mock import MagicMock, patch

from matter_server.client.models.node import MatterNode
import pytest
from typing_extensions import Generator

from homeassistant.components.matter.binary_sensor import (
    DISCOVERY_SCHEMAS as BINARY_SENSOR_SCHEMAS,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(autouse=True)
def binary_sensor_platform() -> Generator[None]:
    """Load only the binary sensor platform."""
    with patch(
        "homeassistant.components.matter.discovery.DISCOVERY_SCHEMAS",
        new={
            Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMAS,
        },
    ):
        yield


@pytest.fixture(name="occupancy_sensor_node")
async def occupancy_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a occupancy sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "occupancy-sensor", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_occupancy_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    occupancy_sensor_node: MatterNode,
) -> None:
    """Test occupancy sensor."""
    state = hass.states.get("binary_sensor.mock_occupancy_sensor_occupancy")
    assert state
    assert state.state == "on"

    set_node_attribute(occupancy_sensor_node, 1, 1030, 0, 0)
    await trigger_subscription_callback(
        hass, matter_client, data=(occupancy_sensor_node.node_id, "1/1030/0", 0)
    )

    state = hass.states.get("binary_sensor.mock_occupancy_sensor_occupancy")
    assert state
    assert state.state == "off"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("fixture", "entity_id"),
    [
        ("eve-contact-sensor", "binary_sensor.eve_door_door"),
        ("leak-sensor", "binary_sensor.water_leak_detector_water_leak"),
    ],
)
async def test_boolean_state_sensors(
    hass: HomeAssistant,
    matter_client: MagicMock,
    fixture: str,
    entity_id: str,
) -> None:
    """Test if binary sensors get created from devices with Boolean State cluster."""
    node = await setup_integration_with_node_fixture(
        hass,
        fixture,
        matter_client,
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    # invert the value
    cur_attr_value = node.get_attribute_value(1, 69, 0)
    set_node_attribute(node, 1, 69, 0, not cur_attr_value)
    await trigger_subscription_callback(
        hass, matter_client, data=(node.node_id, "1/69/0", not cur_attr_value)
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_battery_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    door_lock: MatterNode,
) -> None:
    """Test battery sensor."""
    entity_id = "binary_sensor.mock_door_lock_battery"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    set_node_attribute(door_lock, 1, 47, 14, 1)
    await trigger_subscription_callback(
        hass, matter_client, data=(door_lock.node_id, "1/47/14", 1)
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    entry = entity_registry.async_get(entity_id)

    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
