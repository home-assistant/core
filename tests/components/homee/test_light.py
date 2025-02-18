"""Test homee lights."""

from unittest.mock import MagicMock

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


def mock_attribute_map(attributes) -> dict:
    """Mock the attribute map of a Homee node."""
    attribute_map = {}
    for a in attributes:
        attribute_map[a.type] = a

    return attribute_map


async def setup_mock_light(
    file: str,
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setups the light node for the tests."""
    mock_homee.nodes = [build_mock_node(file)]
    mock_homee.nodes[0].attribute_map = mock_attribute_map(
        mock_homee.nodes[0].attributes
    )
    await setup_integration(hass, mock_config_entry)


async def test_turn_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light."""
    await setup_mock_light("lights.json", hass, mock_homee, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_light_light_1"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 1)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_light_light_1", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 2, 100)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4300,
        },
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    assert calls[0][0] == (1, 2, 100)
    assert calls[1][0] == (1, 4, 4300)
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
            ATTR_HS_COLOR: (100, 100),
        },
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    assert calls[0][0] == (1, 1, 1)
    assert calls[1][0] == (1, 3, 5635840)


async def test_turn_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a light."""
    await setup_mock_light("lights.json", hass, mock_homee, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 0)


async def test_toggle(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling a light."""
    await setup_mock_light("lights.json", hass, mock_homee, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 0)

    mock_homee.nodes[0].attributes[0].current_value = 0.0
    mock_homee.nodes[0].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.nodes[0]
    )
    await hass.async_block_till_done()
    mock_homee.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: "light.test_light_light_1",
        },
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, 1)


async def test_light_attributes(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if lights get the correct supported modes."""
    await setup_mock_light("lights.json", hass, mock_homee, mock_config_entry)

    attributes = hass.states.get("light.test_light_light_1").attributes
    assert attributes["friendly_name"] == "Test Light Light 1"
    assert attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP, ColorMode.HS]
    assert attributes["color_mode"] == ColorMode.HS
    assert attributes["min_color_temp_kelvin"] == 153
    assert attributes["max_color_temp_kelvin"] == 500
    assert attributes["hs_color"] == (35.556, 52.941)
    assert attributes["rgb_color"] == (255, 200, 120)
    assert attributes["xy_color"] == (0.464, 0.402)

    attributes = hass.states.get("light.test_light_light_2").attributes
    assert attributes["friendly_name"] == "Test Light Light 2"
    assert attributes["color_mode"] is None  # Since it is off.
    assert attributes["brightness"] is None
    assert attributes["color_temp_kelvin"] is None
    assert attributes["hs_color"] is None
    assert attributes["min_color_temp_kelvin"] == 2202
    assert attributes["max_color_temp_kelvin"] == 4000

    attributes = hass.states.get("light.test_light_light_3").attributes
    assert attributes["friendly_name"] == "Test Light Light 3"
    assert attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert attributes["brightness"] == 102

    attributes = hass.states.get("light.test_light_light_4").attributes
    assert attributes["friendly_name"] == "Test Light Light 4"
    assert attributes["supported_color_modes"] == [ColorMode.ONOFF]
    assert attributes["color_mode"] is ColorMode.ONOFF


async def test_light_attributes_temp_only(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if lights get the correct supported modes."""
    await setup_mock_light("light_single.json", hass, mock_homee, mock_config_entry)
    attributes = hass.states.get("light.test_light").attributes
    assert attributes["friendly_name"] == "Test Light"
    assert attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert attributes["min_color_temp_kelvin"] == 2000
    assert attributes["max_color_temp_kelvin"] == 7000
