"""Test Matter lights."""


from matter_server.common.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import MockClient, setup_integration_with_node_fixture


@pytest.fixture(name="light_node")
async def light_node_fixture(hass: HomeAssistant) -> MatterNode:
    """Fixture for a light node."""
    return await setup_integration_with_node_fixture(hass, "dimmable-light")


async def test_turn_on(hass: HomeAssistant, light_node: MatterNode) -> None:
    """Test turning on a light."""
    matter_client: MockClient = light_node.matter
    matter_client.mock_command("clusters.OnOff.Commands.On", None)

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_dimmable_light",
        },
        blocking=True,
    )

    assert len(matter_client.mock_sent_commands) == 1
    args = matter_client.mock_sent_commands[0]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1

    matter_client.mock_command(
        "clusters.LevelControl.Commands.MoveToLevelWithOnOff", None
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_dimmable_light",
            "brightness": 128,
        },
        blocking=True,
    )

    assert len(matter_client.mock_sent_commands) == 2
    args = matter_client.mock_sent_commands[1]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1
    assert args["payload"].level == 127
    assert args["payload"].transitionTime == 0


async def test_turn_off(hass: HomeAssistant, light_node: MatterNode) -> None:
    """Test turning off a light."""
    matter_client: MockClient = light_node.matter
    matter_client.mock_command("clusters.OnOff.Commands.Off", None)

    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.mock_dimmable_light",
        },
        blocking=True,
    )

    assert len(matter_client.mock_sent_commands) == 1
    args = matter_client.mock_sent_commands[0]
    assert args["nodeid"] == light_node.node_id
    assert args["endpoint"] == 1
