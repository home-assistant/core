"""Test Alexa capabilities."""
import pytest

from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED, STATE_UNKNOWN
from homeassistant.components.alexa import smart_home
from tests.common import async_mock_service

from . import (
    DEFAULT_CONFIG,
    get_new_request,
    assert_request_calls_service,
    assert_request_fails,
    reported_properties,
)


@pytest.mark.parametrize("result,adjust", [(25, "-5"), (35, "5"), (0, "-80")])
async def test_api_adjust_brightness(hass, result, adjust):
    """Test api adjust brightness process."""
    request = get_new_request(
        "Alexa.BrightnessController", "AdjustBrightness", "light#test"
    )

    # add payload
    request["directive"]["payload"]["brightnessDelta"] = adjust

    # setup test devices
    hass.states.async_set(
        "light.test", "off", {"friendly_name": "Test light", "brightness": "77"}
    )

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["brightness_pct"] == result
    assert msg["header"]["name"] == "Response"


async def test_api_set_color_rgb(hass):
    """Test api set color process."""
    request = get_new_request("Alexa.ColorController", "SetColor", "light#test")

    # add payload
    request["directive"]["payload"]["color"] = {
        "hue": "120",
        "saturation": "0.612",
        "brightness": "0.342",
    }

    # setup test devices
    hass.states.async_set(
        "light.test", "off", {"friendly_name": "Test light", "supported_features": 16}
    )

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["rgb_color"] == (33, 87, 33)
    assert msg["header"]["name"] == "Response"


async def test_api_set_color_temperature(hass):
    """Test api set color temperature process."""
    request = get_new_request(
        "Alexa.ColorTemperatureController", "SetColorTemperature", "light#test"
    )

    # add payload
    request["directive"]["payload"]["colorTemperatureInKelvin"] = "7500"

    # setup test devices
    hass.states.async_set("light.test", "off", {"friendly_name": "Test light"})

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["kelvin"] == 7500
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize("result,initial", [(383, "333"), (500, "500")])
async def test_api_decrease_color_temp(hass, result, initial):
    """Test api decrease color temp process."""
    request = get_new_request(
        "Alexa.ColorTemperatureController", "DecreaseColorTemperature", "light#test"
    )

    # setup test devices
    hass.states.async_set(
        "light.test",
        "off",
        {"friendly_name": "Test light", "color_temp": initial, "max_mireds": 500},
    )

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["color_temp"] == result
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize("result,initial", [(283, "333"), (142, "142")])
async def test_api_increase_color_temp(hass, result, initial):
    """Test api increase color temp process."""
    request = get_new_request(
        "Alexa.ColorTemperatureController", "IncreaseColorTemperature", "light#test"
    )

    # setup test devices
    hass.states.async_set(
        "light.test",
        "off",
        {"friendly_name": "Test light", "color_temp": initial, "min_mireds": 142},
    )

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["color_temp"] == result
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize(
    "domain,payload,source_list,idx",
    [
        ("media_player", "GAME CONSOLE", ["tv", "game console"], 1),
        ("media_player", "SATELLITE TV", ["satellite-tv", "game console"], 0),
        ("media_player", "SATELLITE TV", ["satellite_tv", "game console"], 0),
        ("media_player", "BAD DEVICE", ["satellite_tv", "game console"], None),
    ],
)
async def test_api_select_input(hass, domain, payload, source_list, idx):
    """Test api set input process."""
    hass.states.async_set(
        "media_player.test",
        "off",
        {
            "friendly_name": "Test media player",
            "source": "unknown",
            "source_list": source_list,
        },
    )

    # test where no source matches
    if idx is None:
        await assert_request_fails(
            "Alexa.InputController",
            "SelectInput",
            "media_player#test",
            "media_player.select_source",
            hass,
            payload={"input": payload},
        )
        return

    call, _ = await assert_request_calls_service(
        "Alexa.InputController",
        "SelectInput",
        "media_player#test",
        "media_player.select_source",
        hass,
        payload={"input": payload},
    )
    assert call.data["source"] == source_list[idx]


async def test_report_lock_state(hass):
    """Test LockController implements lockState property."""
    hass.states.async_set("lock.locked", STATE_LOCKED, {})
    hass.states.async_set("lock.unlocked", STATE_UNLOCKED, {})
    hass.states.async_set("lock.unknown", STATE_UNKNOWN, {})

    properties = await reported_properties(hass, "lock.locked")
    properties.assert_equal("Alexa.LockController", "lockState", "LOCKED")

    properties = await reported_properties(hass, "lock.unlocked")
    properties.assert_equal("Alexa.LockController", "lockState", "UNLOCKED")

    properties = await reported_properties(hass, "lock.unknown")
    properties.assert_equal("Alexa.LockController", "lockState", "JAMMED")


async def test_report_dimmable_light_state(hass):
    """Test BrightnessController reports brightness correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {"friendly_name": "Test light On", "brightness": 128, "supported_features": 1},
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {"friendly_name": "Test light Off", "supported_features": 1},
    )

    properties = await reported_properties(hass, "light.test_on")
    properties.assert_equal("Alexa.BrightnessController", "brightness", 50)

    properties = await reported_properties(hass, "light.test_off")
    properties.assert_equal("Alexa.BrightnessController", "brightness", 0)


async def test_report_colored_light_state(hass):
    """Test ColorController reports color correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {
            "friendly_name": "Test light On",
            "hs_color": (180, 75),
            "brightness": 128,
            "supported_features": 17,
        },
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {"friendly_name": "Test light Off", "supported_features": 17},
    )

    properties = await reported_properties(hass, "light.test_on")
    properties.assert_equal(
        "Alexa.ColorController",
        "color",
        {"hue": 180, "saturation": 0.75, "brightness": 128 / 255.0},
    )

    properties = await reported_properties(hass, "light.test_off")
    properties.assert_equal(
        "Alexa.ColorController", "color", {"hue": 0, "saturation": 0, "brightness": 0}
    )


async def test_report_colored_temp_light_state(hass):
    """Test ColorTemperatureController reports color temp correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {"friendly_name": "Test light On", "color_temp": 240, "supported_features": 2},
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {"friendly_name": "Test light Off", "supported_features": 2},
    )

    properties = await reported_properties(hass, "light.test_on")
    properties.assert_equal(
        "Alexa.ColorTemperatureController", "colorTemperatureInKelvin", 4166
    )

    properties = await reported_properties(hass, "light.test_off")
    properties.assert_equal(
        "Alexa.ColorTemperatureController", "colorTemperatureInKelvin", 0
    )


async def test_report_fan_speed_state(hass):
    """Test PercentageController reports fan speed correctly."""
    hass.states.async_set(
        "fan.off",
        "off",
        {"friendly_name": "Off fan", "speed": "off", "supported_features": 1},
    )
    hass.states.async_set(
        "fan.low_speed",
        "on",
        {"friendly_name": "Low speed fan", "speed": "low", "supported_features": 1},
    )
    hass.states.async_set(
        "fan.medium_speed",
        "on",
        {
            "friendly_name": "Medium speed fan",
            "speed": "medium",
            "supported_features": 1,
        },
    )
    hass.states.async_set(
        "fan.high_speed",
        "on",
        {"friendly_name": "High speed fan", "speed": "high", "supported_features": 1},
    )

    properties = await reported_properties(hass, "fan.off")
    properties.assert_equal("Alexa.PercentageController", "percentage", 0)

    properties = await reported_properties(hass, "fan.low_speed")
    properties.assert_equal("Alexa.PercentageController", "percentage", 33)

    properties = await reported_properties(hass, "fan.medium_speed")
    properties.assert_equal("Alexa.PercentageController", "percentage", 66)

    properties = await reported_properties(hass, "fan.high_speed")
    properties.assert_equal("Alexa.PercentageController", "percentage", 100)


async def test_report_cover_percentage_state(hass):
    """Test PercentageController reports cover percentage correctly."""
    hass.states.async_set(
        "cover.fully_open",
        "open",
        {
            "friendly_name": "Fully open cover",
            "current_position": 100,
            "supported_features": 15,
        },
    )
    hass.states.async_set(
        "cover.half_open",
        "open",
        {
            "friendly_name": "Half open cover",
            "current_position": 50,
            "supported_features": 15,
        },
    )
    hass.states.async_set(
        "cover.closed",
        "closed",
        {
            "friendly_name": "Closed cover",
            "current_position": 0,
            "supported_features": 15,
        },
    )

    properties = await reported_properties(hass, "cover.fully_open")
    properties.assert_equal("Alexa.PercentageController", "percentage", 100)

    properties = await reported_properties(hass, "cover.half_open")
    properties.assert_equal("Alexa.PercentageController", "percentage", 50)

    properties = await reported_properties(hass, "cover.closed")
    properties.assert_equal("Alexa.PercentageController", "percentage", 0)
