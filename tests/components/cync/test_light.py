"""Tests for the Cync integration light platform."""

from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.util.color import value_to_brightness
from homeassistant.util.scaling import scale_ranged_value_to_int_range

from . import setup_integration

from tests.common import MockConfigEntry


async def test_light_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that light attributes are properly set on setup."""

    await setup_integration(hass, mock_config_entry)

    # test light set to use color temperature
    bedroom_light = hass.states.get("light.bedroom_lamp")
    assert bedroom_light is not None
    assert bedroom_light.attributes["friendly_name"] == "Bedroom Lamp"
    assert bedroom_light.state == "on"
    assert bedroom_light.attributes["brightness"] == value_to_brightness((0, 100), 80)
    min_color_temp = bedroom_light.attributes["min_color_temp_kelvin"]
    max_color_temp = bedroom_light.attributes["max_color_temp_kelvin"]
    assert bedroom_light.attributes[
        "color_temp_kelvin"
    ] == scale_ranged_value_to_int_range(
        (1, 100),
        (min_color_temp, max_color_temp),
        20,
    )
    assert bedroom_light.attributes["color_mode"] == ColorMode.COLOR_TEMP

    # test light set to use RGB
    office_light_1 = hass.states.get("light.lamp_bulb_1")
    assert office_light_1 is not None
    assert office_light_1.attributes["friendly_name"] == "Lamp Bulb 1"
    assert office_light_1.state == "on"
    assert office_light_1.attributes["brightness"] == value_to_brightness((0, 100), 90)
    assert office_light_1.attributes["color_mode"] == ColorMode.RGB
    assert office_light_1.attributes["rgb_color"] == (120, 145, 180)

    # test light which is unresponsive
    office_light_2 = hass.states.get("light.lamp_bulb_2")
    assert office_light_2 is not None
    assert office_light_2.attributes["friendly_name"] == "Lamp Bulb 2"
    assert office_light_2.state == "unavailable"
