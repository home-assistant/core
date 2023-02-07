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
        hass, "extended-color-light", matter_client
    )


async def test_turn_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test turning on a light."""

    # OnOff test
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
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

    # Brightness test
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
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
    matter_client.send_device_command.reset_mock()

    # HS Color test
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "hs_color": [0, 0],
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToHueAndSaturation(
                    hue=0,
                    saturation=0,
                    transitionTime=0,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # XY Color test
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "xy_color": [0.5, 0.5],
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToColor(
                    colorX=(0.5 * 65536),
                    colorY=(0.5 * 65536),
                    transitionTime=0,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Color Temperature test
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "color_temp": 300,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperature=300,
                    transitionTime=0,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.state == "on"

    # HS Color Test
    set_node_attribute(light_node, 1, 768, 8, 0)
    set_node_attribute(light_node, 1, 768, 1, 50)
    set_node_attribute(light_node, 1, 768, 0, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.attributes["color_mode"] == "hs"
    assert state.attributes["hs_color"] == (141.732, 19.685)

    # XY Color Test
    set_node_attribute(light_node, 1, 768, 8, 1)
    set_node_attribute(light_node, 1, 768, 3, 50)
    set_node_attribute(light_node, 1, 768, 4, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.attributes["color_mode"] == "xy"
    assert state.attributes["xy_color"] == (0.0007630, 0.001526)

    # Color Temperature Test
    set_node_attribute(light_node, 1, 768, 8, 2)
    set_node_attribute(light_node, 1, 768, 7, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.attributes["color_mode"] == "color_temp"
    assert state.attributes["color_temp"] == 100

    # Brightness state test
    set_node_attribute(light_node, 1, 8, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.attributes["brightness"] == 49

    # Off state test
    set_node_attribute(light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.state == "off"


async def test_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
) -> None:
    """Test turning off a light."""
    state = hass.states.get("light.mock_extended_color_light")
    assert state
    assert state.state == "on"

    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.mock_extended_color_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
