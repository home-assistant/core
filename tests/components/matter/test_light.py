"""Test Matter lights."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.common.models.node import MatterNode
import pytest

from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="on_off_light_node")
async def on_off_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an on/off light node."""
    return await setup_integration_with_node_fixture(hass, "onoff-light", matter_client)


@pytest.fixture(name="dimmable_light_node")
async def dimmable_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a dimmable light node."""
    return await setup_integration_with_node_fixture(
        hass, "dimmable-light", matter_client
    )


@pytest.fixture(name="color_temperature_light_node")
async def color_temperature_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a color temperature light node."""
    return await setup_integration_with_node_fixture(
        hass, "color-temperature-light", matter_client
    )


@pytest.fixture(name="extended_color_light_node")
async def extended_color_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an extended color light node."""
    return await setup_integration_with_node_fixture(
        hass, "extended-color-light", matter_client
    )


# @pytest.fixture(name="light_node")
# async def extended_color_light_node_fixture(
#    hass: HomeAssistant, matter_client: MagicMock
# ) -> MatterNode:
#    """Fixture for an extended color light node."""
#    return await setup_integration_with_node_fixture(
#        hass, "extended-color-light", matter_client
#    )


async def test_on_off_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    on_off_light_node: MatterNode,
) -> None:
    """Test an on/off light."""

    # Test that the light is off
    set_node_attribute(on_off_light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_onoff_light")
    assert state is not None
    assert state.state == "off"

    # Test that the light is on
    set_node_attribute(on_off_light_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_onoff_light")
    assert state is not None
    assert state.state == "on"

    # Turn the light off
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.mock_onoff_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=on_off_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_onoff_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=on_off_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()


async def test_dimmable_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    dimmable_light_node: MatterNode,
) -> None:
    """Test a dimmable light."""
    # Test that the light is off
    set_node_attribute(dimmable_light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_dimmable_light")
    assert state is not None
    assert state.state == "off"

    # Test that the light is on
    set_node_attribute(dimmable_light_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_dimmable_light")
    assert state is not None
    assert state.state == "on"

    # Test that the light brightness is 50 (out of 254)
    set_node_attribute(dimmable_light_node, 1, 8, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_dimmable_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 49

    # Turn the light off
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
        node_id=dimmable_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on
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
        node_id=dimmable_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()

    # Change brightness
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
        node_id=dimmable_light_node.node_id,
        endpoint=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128,
            transitionTime=0,
        ),
    )
    matter_client.send_device_command.reset_mock()


async def test_color_temperature_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    color_temperature_light_node: MatterNode,
) -> None:
    """Test a color temperature light."""

    set_node_attribute(color_temperature_light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_color_temperature_light")
    assert state is not None
    assert state.state == "off"

    # Test that the light is on
    set_node_attribute(color_temperature_light_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_color_temperature_light")
    assert state is not None
    assert state.state == "on"

    # Test the brightness is 50 (out of 254)
    set_node_attribute(color_temperature_light_node, 1, 8, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_color_temperature_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 49

    # Test that the light color temperature is 3000 (out of 50000)
    set_node_attribute(color_temperature_light_node, 1, 768, 8, 2)
    set_node_attribute(color_temperature_light_node, 1, 768, 7, 3000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_color_temperature_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 3003

    # Turn the light off
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.mock_color_temperature_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=color_temperature_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_color_temperature_light",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=color_temperature_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()

    # Change brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_color_temperature_light",
            "brightness": 128,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=color_temperature_light_node.node_id,
        endpoint=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128,
            transitionTime=0,
        ),
    )
    matter_client.send_device_command.reset_mock()

    # Change color temperature
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_color_temperature_light",
            "color_temp": 3000,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=color_temperature_light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperature=3003,
                    transitionTime=0,
                ),
            ),
            call(
                node_id=color_temperature_light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()


async def test_extended_color_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    extended_color_light_node: MatterNode,
) -> None:
    """Test an extended color light."""
    set_node_attribute(extended_color_light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "off"

    # Test that the light is on
    set_node_attribute(extended_color_light_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "on"

    # Test that the light brightness is 50 (out of 254)
    set_node_attribute(extended_color_light_node, 1, 8, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 49

    # Test that the color temperature changes
    set_node_attribute(extended_color_light_node, 1, 768, 8, 2)
    set_node_attribute(extended_color_light_node, 1, 768, 7, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 100

    # Test that the XY color changes
    set_node_attribute(extended_color_light_node, 1, 768, 8, 1)
    set_node_attribute(extended_color_light_node, 1, 768, 3, 50)
    set_node_attribute(extended_color_light_node, 1, 768, 4, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.XY
    assert state.attributes["xy_color"] == (0.0007630, 0.001526)

    # Test that the HS color changes
    set_node_attribute(extended_color_light_node, 1, 768, 8, 0)
    set_node_attribute(extended_color_light_node, 1, 768, 1, 50)
    set_node_attribute(extended_color_light_node, 1, 768, 0, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("light.mock_extended_color_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["hs_color"] == (141.732, 19.685)

    # Turn the light off
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
        node_id=extended_color_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on
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
        node_id=extended_color_light_node.node_id,
        endpoint=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with brightness
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
        node_id=extended_color_light_node.node_id,
        endpoint=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128, transitionTime=0
        ),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with color temperature
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "color_temp": 100,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperature=100, transitionTime=0
                ),
            ),
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with XY color
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "xy_color": (0.5, 0.5),
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToColor(
                    colorX=0.5 * 65536, colorY=0.5 * 65536, transitionTime=0
                ),
            ),
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with HS color
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.mock_extended_color_light",
            "hs_color": (0, 0),
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.ColorControl.Commands.MoveToHueAndSaturation(
                    hue=0, saturation=0, transitionTime=0
                ),
            ),
            call(
                node_id=extended_color_light_node.node_id,
                endpoint=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()
