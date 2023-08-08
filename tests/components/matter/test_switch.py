"""Test Matter switches."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="switch_node")
async def switch_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a switch node."""
    return await setup_integration_with_node_fixture(
        hass, "on-off-plugin-unit", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_turn_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    switch_node: MatterNode,
) -> None:
    """Test turning on a switch."""
    state = hass.states.get("switch.mock_onoffpluginunit_powerplug_switch")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {
            "entity_id": "switch.mock_onoffpluginunit_powerplug_switch",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=switch_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.On(),
    )

    set_node_attribute(switch_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("switch.mock_onoffpluginunit_powerplug_switch")
    assert state
    assert state.state == "on"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    switch_node: MatterNode,
) -> None:
    """Test turning off a switch."""
    state = hass.states.get("switch.mock_onoffpluginunit_powerplug_switch")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {
            "entity_id": "switch.mock_onoffpluginunit_powerplug_switch",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=switch_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )
