"""Test Matter lights."""
from typing import Any

from matter_server.client.model.node import MatterNode
from matter_server.vendor.chip.clusters import Objects as clusters
import pytest

from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture


@pytest.fixture(name="light_node")
async def light_node_fixture(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> MatterNode:
    """Fixture for a light node."""
    return await setup_integration_with_node_fixture(
        hass, hass_storage, "lighting-example-app"
    )


async def test_turn_on(hass: HomeAssistant, light_node: MatterNode) -> None:
    """Test turning on a light."""
    light_node.matter.client.mock_command(clusters.OnOff.Commands.On, None)

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.my_cool_light",
        },
        blocking=True,
    )

    assert len(light_node.matter.client.mock_sent_commands) == 1
    args = light_node.matter.client.mock_sent_commands[0]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1

    light_node.matter.client.mock_command(
        clusters.LevelControl.Commands.MoveToLevelWithOnOff, None
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.my_cool_light",
            "brightness": 128,
        },
        blocking=True,
    )

    assert len(light_node.matter.client.mock_sent_commands) == 2
    args = light_node.matter.client.mock_sent_commands[1]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1
    assert args["payload"].level == 127
    assert args["payload"].transitionTime == 0


async def test_turn_off(hass: HomeAssistant, light_node: MatterNode) -> None:
    """Test turning off a light."""
    light_node.matter.client.mock_command(clusters.OnOff.Commands.Off, None)

    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.my_cool_light",
        },
        blocking=True,
    )

    assert len(light_node.matter.client.mock_sent_commands) == 1
    args = light_node.matter.client.mock_sent_commands[0]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1
