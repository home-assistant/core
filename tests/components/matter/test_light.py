"""Test Matter lights."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.common.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="light_node")
async def light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a light node."""
    return await setup_integration_with_node_fixture(
        hass, "dimmable-light", matter_client
    )


async def test_turn_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test turning on a light."""
    state = hass.states.get("light.mock_dimmable_light")
    assert state
    assert state.state == "on"

    set_node_attribute(light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_dimmable_light")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_dimmable_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_dimmable_light",
            "brightness": 128,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128,
            transitionTime=0,
        ),
    )


async def test_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test turning off a light."""
    state = hass.states.get("light.mock_dimmable_light")
    assert state
    assert state.state == "on"

    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.mock_dimmable_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
