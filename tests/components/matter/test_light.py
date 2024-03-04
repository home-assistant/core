"""Test Matter lights."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
import pytest

from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("fixture", "entity_id"),
    [
        ("extended-color-light", "light.mock_extended_color_light"),
        ("color-temperature-light", "light.mock_color_temperature_light"),
        ("dimmable-light", "light.mock_dimmable_light"),
        ("onoff-light", "light.mock_onoff_light"),
    ],
)
async def test_on_off_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    fixture: str,
    entity_id: str,
) -> None:
    """Test an on/off light."""

    light_node = await setup_integration_with_node_fixture(
        hass,
        fixture,
        matter_client,
    )

    # Test that the light is off
    set_node_attribute(light_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Test that the light is on
    set_node_attribute(light_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Turn the light off
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.On(),
    )
    matter_client.send_device_command.reset_mock()


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("fixture", "entity_id"),
    [
        ("extended-color-light", "light.mock_extended_color_light"),
        ("color-temperature-light", "light.mock_color_temperature_light"),
        ("dimmable-light", "light.mock_dimmable_light"),
    ],
)
async def test_dimmable_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    fixture: str,
    entity_id: str,
) -> None:
    """Test a dimmable light."""

    light_node = await setup_integration_with_node_fixture(
        hass,
        fixture,
        matter_client,
    )

    # Test that the light brightness is 50 (out of 254)
    set_node_attribute(light_node, 1, 8, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 49

    # Change brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entity_id,
            "brightness": 128,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint_id=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128,
            transitionTime=2,
        ),
    )
    matter_client.send_device_command.reset_mock()

    # Change brightness with custom transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": 128, "transition": 3},
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=light_node.node_id,
        endpoint_id=1,
        command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
            level=128,
            transitionTime=30,
        ),
    )
    matter_client.send_device_command.reset_mock()


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("fixture", "entity_id"),
    [
        ("extended-color-light", "light.mock_extended_color_light"),
        ("color-temperature-light", "light.mock_color_temperature_light"),
    ],
)
async def test_color_temperature_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    fixture: str,
    entity_id: str,
) -> None:
    """Test a color temperature light."""

    light_node = await setup_integration_with_node_fixture(
        hass,
        fixture,
        matter_client,
    )

    # Test that the light color temperature is 3000 (out of 50000)
    set_node_attribute(light_node, 1, 768, 8, 2)
    set_node_attribute(light_node, 1, 768, 7, 3000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 3003

    # Change color temperature
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entity_id,
            "color_temp": 300,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperatureMireds=300,
                    transitionTime=2,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Change color temperature with custom transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "color_temp": 300, "transition": 4.0},
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperatureMireds=300,
                    transitionTime=40,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("fixture", "entity_id"),
    [
        ("extended-color-light", "light.mock_extended_color_light"),
    ],
)
async def test_extended_color_light(
    hass: HomeAssistant,
    matter_client: MagicMock,
    fixture: str,
    entity_id: str,
) -> None:
    """Test an extended color light."""

    light_node = await setup_integration_with_node_fixture(
        hass,
        fixture,
        matter_client,
    )

    # Test that the XY color changes
    set_node_attribute(light_node, 1, 768, 8, 1)
    set_node_attribute(light_node, 1, 768, 3, 50)
    set_node_attribute(light_node, 1, 768, 4, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.XY
    assert state.attributes["xy_color"] == (0.0007630, 0.001526)

    # Test that the HS color changes
    set_node_attribute(light_node, 1, 768, 8, 0)
    set_node_attribute(light_node, 1, 768, 1, 50)
    set_node_attribute(light_node, 1, 768, 0, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["hs_color"] == (141.732, 19.685)

    # Turn the light on with XY color
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entity_id,
            "xy_color": (0.5, 0.5),
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToColor(
                    colorX=0.5 * 65536,
                    colorY=0.5 * 65536,
                    transitionTime=2,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with XY color and custom transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "xy_color": (0.5, 0.5), "transition": 4.0},
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToColor(
                    colorX=0.5 * 65536,
                    colorY=0.5 * 65536,
                    transitionTime=40,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
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
            "entity_id": entity_id,
            "hs_color": (236.69291338582678, 100.0),
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=1,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToHueAndSaturation(
                    hue=167,
                    saturation=254,
                    transitionTime=2,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()

    # Turn the light on with HS color and custom transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entity_id,
            "hs_color": (236.69291338582678, 100.0),
            "transition": 4.0,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    matter_client.send_device_command.assert_has_calls(
        [
            call(
                node_id=1,
                endpoint_id=1,
                command=clusters.ColorControl.Commands.MoveToHueAndSaturation(
                    hue=167,
                    saturation=254,
                    transitionTime=40,
                    optionsMask=1,
                    optionsOverride=1,
                ),
            ),
            call(
                node_id=light_node.node_id,
                endpoint_id=1,
                command=clusters.OnOff.Commands.On(),
            ),
        ]
    )
    matter_client.send_device_command.reset_mock()
