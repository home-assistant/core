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


@pytest.fixture(name="microwave_oven_node")
async def microwave_oven_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a microwave oven node."""
    return await setup_integration_with_node_fixture(
        hass, "microwave-oven", matter_client
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
async def test_microwave_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    microwave_oven_node: MatterNode,
) -> None:
    """Test select entities are created for the MicrowaveOvenMode cluster attributes."""
    state = hass.states.get("select.microwave_oven_mode")
    assert state
    assert state.state == "Normal"
    assert state.attributes["options"] == [
        "Normal",
        "Defrost",
    ]
    # name should just be Mode (from the translation key)
    assert state.attributes["friendly_name"] == "Microwave Oven Mode"
    set_node_attribute(microwave_oven_node, 1, 94, 1, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.microwave_oven_mode")
    assert state.state == "Defrost"
