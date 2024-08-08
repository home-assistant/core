"""Test Matter select entities."""

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


@pytest.fixture(name="light_node")
async def dimmable_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a dimmable light node."""
    return await setup_integration_with_node_fixture(
        hass, "dimmable-light", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_mode_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test select entities are created for the ModeSelect cluster attributes."""
    state = hass.states.get("select.mock_dimmable_light_led_color")
    assert state
    assert state.state == "Aqua"
    assert state.attributes["options"] == [
        "Red",
        "Orange",
        "Lemon",
        "Lime",
        "Green",
        "Teal",
        "Cyan",
        "Aqua",
        "Blue",
        "Violet",
        "Magenta",
        "Pink",
        "White",
    ]
    # name should be derived from description attribute
    assert state.attributes["friendly_name"] == "Mock Dimmable Light LED Color"
    set_node_attribute(light_node, 6, 80, 3, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.mock_dimmable_light_led_color")
    assert state.state == "Orange"
    # test select option
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.mock_dimmable_light_led_color",
            "option": "Lime",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint_id=6,
        command=clusters.ModeSelect.Commands.ChangeToMode(newMode=3),
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_attribute_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test select entities are created for attribute based discovery schema(s)."""
    entity_id = "select.mock_dimmable_light_power_on_behavior_on_startup"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Previous"
    assert state.attributes["options"] == ["On", "Off", "Toggle", "Previous"]
    assert (
        state.attributes["friendly_name"]
        == "Mock Dimmable Light Power-on behavior on Startup"
    )
    set_node_attribute(light_node, 1, 6, 16387, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "On"
