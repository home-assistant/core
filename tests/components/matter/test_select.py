"""Test Matter select entities."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test selects."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_mode_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
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
    set_node_attribute(matter_node, 6, 80, 3, 1)
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
        node_id=matter_node.node_id,
        endpoint_id=6,
        command=clusters.ModeSelect.Commands.ChangeToMode(newMode=3),
    )


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_attribute_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test select entities are created for attribute based discovery schema(s)."""
    entity_id = "select.mock_dimmable_light_power_on_behavior_on_startup"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "previous"
    assert state.attributes["options"] == ["on", "off", "toggle", "previous"]
    assert (
        state.attributes["friendly_name"]
        == "Mock Dimmable Light Power-on behavior on startup"
    )
    set_node_attribute(matter_node, 1, 6, 16387, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "on"
    # test that an invalid value (e.g. 253) leads to an unknown state
    set_node_attribute(matter_node, 1, 6, 16387, 253)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "unknown"
