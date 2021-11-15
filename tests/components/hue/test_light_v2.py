"""Philips Hue lights platform tests for V2 bridge/api."""

from homeassistant.components import hue
from homeassistant.components.light import COLOR_MODE_COLOR_TEMP, COLOR_MODE_XY

from .conftest import create_config_entry

HUE_LIGHT_NS = "homeassistant.components.light.hue."


async def setup_bridge(hass, mock_bridge_v2):
    """Load the Hue light platform with the provided bridge."""
    hass.config.components.add(hue.DOMAIN)
    config_entry = create_config_entry(api_version=2)
    mock_bridge_v2.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge_v2}
    await hass.config_entries.async_forward_entry_setup(config_entry, "light")
    # await hass.async_block_till_done()


async def test_lights(hass, mock_bridge_v2, v2_resources_test_data):
    """Test if all v2 lights get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_bridge(hass, mock_bridge_v2)
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 8 lights
    assert len(hass.states.async_all()) == 8

    # test light which supports color and color temperature
    light_1 = hass.states.get("light.hue_light_with_color_and_color_temperature_1")
    assert light_1 is not None
    assert (
        light_1.attributes["friendly_name"]
        == "Hue light with color and color temperature 1"
    )
    assert light_1.state == "on"
    assert light_1.attributes["brightness"] == int(46.85 / 100 * 255)
    assert light_1.attributes["mode"] == "normal"
    assert light_1.attributes["color_mode"] == COLOR_MODE_XY
    assert set(light_1.attributes["supported_color_modes"]) == {
        COLOR_MODE_COLOR_TEMP,
        COLOR_MODE_XY,
    }
    assert light_1.attributes["xy_color"] == (0.5614, 0.4058)
    assert light_1.attributes["min_mireds"] == 153
    assert light_1.attributes["max_mireds"] == 500
    assert light_1.attributes["dynamics"] == "dynamic_palette"

    # test light which supports color temperature only
    light_2 = hass.states.get("light.hue_light_with_color_temperature_only")
    assert light_2 is not None
    assert (
        light_2.attributes["friendly_name"] == "Hue light with color temperature only"
    )
    assert light_2.state == "off"
    assert light_2.attributes["mode"] == "normal"
    assert light_2.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]
    assert light_2.attributes["min_mireds"] == 153
    assert light_2.attributes["max_mireds"] == 454
    assert light_2.attributes["dynamics"] == "none"

    # test light which supports color only
    light_3 = hass.states.get("light.hue_light_with_color_only")
    assert light_3 is not None
    assert light_3.attributes["friendly_name"] == "Hue light with color only"
    assert light_3.state == "on"
    assert light_3.attributes["brightness"] == 128
    assert light_3.attributes["mode"] == "normal"
    assert light_3.attributes["supported_color_modes"] == [COLOR_MODE_XY]
    assert light_3.attributes["color_mode"] == COLOR_MODE_XY
    assert light_3.attributes["dynamics"] == "dynamic_palette"

    # test light which supports on/off only
    light_4 = hass.states.get("light.hue_on_off_light")
    assert light_4 is not None
    assert light_4.attributes["friendly_name"] == "Hue on/off light"
    assert light_4.state == "off"
    assert light_4.attributes["mode"] == "normal"
    assert light_4.attributes["supported_color_modes"] == []

    # test light created for hue zone
    light_5 = hass.states.get("light.test_zone")
    assert light_5 is not None
    assert light_5.attributes["friendly_name"] == "Test Zone"
    assert light_5.state == "on"
    assert light_5.attributes["brightness"] == 119
    assert light_5.attributes["color_mode"] == COLOR_MODE_XY
    assert set(light_5.attributes["supported_color_modes"]) == {
        COLOR_MODE_COLOR_TEMP,
        COLOR_MODE_XY,
    }
    assert light_5.attributes["min_mireds"] == 153
    assert light_5.attributes["max_mireds"] == 500
    assert light_5.attributes["is_hue_group"] is True
    assert light_5.attributes["hue_scenes"] == {"Dynamic Test Scene"}
    assert light_5.attributes["hue_type"] == "zone"
    assert light_5.attributes["lights"] == {
        "Hue light with color and color temperature 1",
        "Hue light with color and color temperature gradient",
        "Hue light with color and color temperature 2",
    }

    # test light created for hue room
    light_6 = hass.states.get("light.test_room")
    assert light_6 is not None
    assert light_6.attributes["friendly_name"] == "Test Room"
    assert light_6.state == "off"
    assert light_6.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]
    assert light_6.attributes["min_mireds"] == 153
    assert light_6.attributes["max_mireds"] == 454
    assert light_6.attributes["is_hue_group"] is True
    assert light_6.attributes["hue_scenes"] == {"Regular Test Scene"}
    assert light_6.attributes["hue_type"] == "room"
    assert light_6.attributes["lights"] == {
        "Hue on/off light",
        "Hue light with color temperature only",
    }
