"""Test Matter valve."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture


@pytest.fixture(name="valve_node")
async def valve_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a valve node."""
    return await setup_integration_with_node_fixture(hass, "valve", matter_client)


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_valve(
    hass: HomeAssistant,
    matter_client: MagicMock,
    valve_node: MatterNode,
) -> None:
    """Test valve entity is created for a Matter ValveConfigurationAndControl Cluster."""
    entity_id = "valve.valve_valve"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["friendly_name"] == "Valve Valve"

    await hass.services.async_call(
        "valve",
        "close_valve",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=valve_node.node_id,
        endpoint_id=1,
        command=clusters.ValveConfigurationAndControl.Commands.Close(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "valve",
        "open_valve",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=valve_node.node_id,
        endpoint_id=1,
        command=clusters.ValveConfigurationAndControl.Commands.Open(),
    )
    matter_client.send_device_command.reset_mock()
