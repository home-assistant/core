"""Test Alexa capabilities."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.alexa import smart_home
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.lock import LockState
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.components.water_heater import (
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_GAS,
    STATE_HEAT_PUMP,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from .test_common import (
    assert_request_calls_service,
    assert_request_fails,
    get_default_config,
    get_new_request,
    reported_properties,
)

from tests.common import async_mock_service


@pytest.mark.parametrize(
    (
        "current_activity",
        "activity_list",
    ),
    [
        ("TV", ["TV", "MUSIC", "DVD"]),
        ("TV", ["TV"]),
    ],
)
async def test_discovery_remote(
    hass: HomeAssistant, current_activity: str, activity_list: list[str]
) -> None:
    """Test discory for a remote entity."""
    request = get_new_request("Alexa.Discovery", "Discover")
    # setup test device
    hass.states.async_set(
        "remote.test",
        "off",
        {
            "current_activity": current_activity,
            "activity_list": activity_list,
            "supported_features": 4,
        },
    )
    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    assert "event" in msg
    msg = msg["event"]
    assert len(msg["payload"]["endpoints"]) == 1
    endpoint = msg["payload"]["endpoints"][0]
    assert endpoint["endpointId"] == "remote#test"
    interfaces = {capability["interface"] for capability in endpoint["capabilities"]}
    assert "Alexa.PowerController" in interfaces
    assert "Alexa.ModeController" in interfaces


@pytest.mark.parametrize("adjust", ["-5", "5", "-80"])
async def test_api_adjust_brightness(hass: HomeAssistant, adjust: str) -> None:
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

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["brightness_step_pct"] == int(adjust)
    assert msg["header"]["name"] == "Response"


async def test_api_set_color_rgb(hass: HomeAssistant) -> None:
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

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["rgb_color"] == (33, 87, 33)
    assert msg["header"]["name"] == "Response"


async def test_api_set_color_temperature(hass: HomeAssistant) -> None:
    """Test api set color temperature process."""
    request = get_new_request(
        "Alexa.ColorTemperatureController", "SetColorTemperature", "light#test"
    )

    # add payload
    request["directive"]["payload"]["colorTemperatureInKelvin"] = "7500"

    # setup test devices
    hass.states.async_set("light.test", "off", {"friendly_name": "Test light"})

    call_light = async_mock_service(hass, "light", "turn_on")

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["kelvin"] == 7500
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize(("result", "initial"), [(383, "333"), (500, "500")])
async def test_api_decrease_color_temp(
    hass: HomeAssistant, result: int, initial: str
) -> None:
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

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["color_temp"] == result
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize(("result", "initial"), [(283, "333"), (142, "142")])
async def test_api_increase_color_temp(
    hass: HomeAssistant, result: int, initial: str
) -> None:
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

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert "event" in msg
    msg = msg["event"]

    assert len(call_light) == 1
    assert call_light[0].data["entity_id"] == "light.test"
    assert call_light[0].data["color_temp"] == result
    assert msg["header"]["name"] == "Response"


@pytest.mark.parametrize(
    ("domain", "payload", "source_list", "idx"),
    [
        ("media_player", "GAME CONSOLE", ["tv", "game console", 10000], 1),
        ("media_player", "SATELLITE TV", ["satellite-tv", "game console", None], 0),
        ("media_player", "SATELLITE TV", ["satellite_tv", "game console"], 0),
    ],
)
async def test_api_select_input(
    hass: HomeAssistant,
    domain: str,
    payload: str,
    source_list: list[Any],
    idx: int | None,
) -> None:
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

    call, _ = await assert_request_calls_service(
        "Alexa.InputController",
        "SelectInput",
        "media_player#test",
        "media_player.select_source",
        hass,
        payload={"input": payload},
    )
    assert call.data["source"] == source_list[idx]


@pytest.mark.parametrize(
    ("source_list"),
    [(["satellite_tv", "game console"]), ([])],
)
async def test_api_select_input_fails(
    hass: HomeAssistant,
    source_list: list[Any],
) -> None:
    """Test api set input process fails."""
    hass.states.async_set(
        "media_player.test",
        "off",
        {
            "friendly_name": "Test media player",
            "source": "unknown",
            "source_list": source_list,
        },
    )
    await assert_request_fails(
        "Alexa.InputController",
        "SelectInput",
        "media_player#test",
        "media_player.select_source",
        hass,
        payload={"input": "BAD DEVICE"},
    )


@pytest.mark.parametrize(
    ("activity", "activity_list", "target_activity_index"),
    [
        ("TV", ["TV", "MUSIC", "DVD"], 0),
        ("MUSIC", ["TV", "MUSIC", "DVD", 1000], 1),
        ("DVD", ["TV", "MUSIC", "DVD", None], 2),
        ("TV", ["TV"], 0),
    ],
)
async def test_api_select_activity(
    hass: HomeAssistant,
    activity: str,
    activity_list: list[str],
    target_activity_index: int | None,
) -> None:
    """Test api set activity process."""
    hass.states.async_set(
        "remote.test",
        "off",
        {
            "current_activity": activity,
            "activity_list": activity_list,
        },
    )
    call, _ = await assert_request_calls_service(
        "Alexa.ModeController",
        "SetMode",
        "remote#test",
        "remote.turn_on",
        hass,
        payload={"mode": f"activity.{activity}"},
        instance="remote.activity",
    )
    assert call.data["activity"] == activity_list[target_activity_index]


@pytest.mark.parametrize(("activity_list"), [(["TV", "MUSIC", "DVD"]), ([])])
async def test_api_select_activity_fails(
    hass: HomeAssistant, activity_list: list[str]
) -> None:
    """Test api set activity process fails."""
    hass.states.async_set(
        "remote.test",
        "off",
        {
            "current_activity": None,
            "activity_list": activity_list,
        },
    )
    await assert_request_fails(
        "Alexa.ModeController",
        "SetMode",
        "remote#test",
        "remote.turn_on",
        hass,
        payload={"mode": "activity.BAD"},
        instance="remote.activity",
    )


@pytest.mark.parametrize(
    (
        "current_state",
        "target_name",
        "target_service",
    ),
    [
        ("on", "TurnOff", "turn_off"),
        ("off", "TurnOn", "turn_on"),
    ],
)
async def test_api_remote_set_power_state(
    hass: HomeAssistant,
    current_state: str,
    target_name: str,
    target_service: str,
) -> None:
    """Test api remote set power state process."""
    hass.states.async_set(
        "remote.test",
        current_state,
        {
            "current_activity": ["TV", "MUSIC", "DVD"],
            "activity_list": "TV",
        },
    )

    _, msg = await assert_request_calls_service(
        "Alexa.PowerController",
        target_name,
        "remote#test",
        f"remote.{target_service}",
        hass,
    )


async def test_report_lock_state(hass: HomeAssistant) -> None:
    """Test LockController implements lockState property."""
    hass.states.async_set("lock.locked", LockState.LOCKED, {})
    hass.states.async_set("lock.unlocked", LockState.UNLOCKED, {})
    hass.states.async_set("lock.unlocking", LockState.UNLOCKING, {})
    hass.states.async_set("lock.locking", LockState.LOCKING, {})
    hass.states.async_set("lock.jammed", LockState.JAMMED, {})
    hass.states.async_set("lock.unknown", STATE_UNKNOWN, {})

    properties = await reported_properties(hass, "lock.locked")
    properties.assert_equal("Alexa.LockController", "lockState", "LOCKED")

    properties = await reported_properties(hass, "lock.unlocking")
    properties.assert_equal("Alexa.LockController", "lockState", "LOCKED")

    properties = await reported_properties(hass, "lock.unlocked")
    properties.assert_equal("Alexa.LockController", "lockState", "UNLOCKED")

    properties = await reported_properties(hass, "lock.locking")
    properties.assert_equal("Alexa.LockController", "lockState", "UNLOCKED")

    properties = await reported_properties(hass, "lock.unknown")
    properties.assert_equal("Alexa.LockController", "lockState", "JAMMED")

    properties = await reported_properties(hass, "lock.jammed")
    properties.assert_equal("Alexa.LockController", "lockState", "JAMMED")


@pytest.mark.parametrize(
    "supported_color_modes", [["brightness"], ["hs"], ["color_temp"]]
)
async def test_report_dimmable_light_state(
    hass: HomeAssistant, supported_color_modes: list[str]
) -> None:
    """Test BrightnessController reports brightness correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {
            "friendly_name": "Test light On",
            "brightness": 128,
            "supported_color_modes": supported_color_modes,
        },
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {
            "friendly_name": "Test light Off",
            "supported_color_modes": supported_color_modes,
        },
    )

    properties = await reported_properties(hass, "light.test_on")
    properties.assert_equal("Alexa.BrightnessController", "brightness", 50)

    properties = await reported_properties(hass, "light.test_off")
    properties.assert_equal("Alexa.BrightnessController", "brightness", 0)


@pytest.mark.parametrize("supported_color_modes", [["hs"], ["rgb"], ["xy"]])
async def test_report_colored_light_state(
    hass: HomeAssistant, supported_color_modes: list[str]
) -> None:
    """Test ColorController reports color correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {
            "friendly_name": "Test light On",
            "hs_color": (180, 75),
            "brightness": 128,
            "supported_color_modes": supported_color_modes,
        },
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {
            "friendly_name": "Test light Off",
            "supported_color_modes": supported_color_modes,
        },
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


async def test_report_colored_temp_light_state(hass: HomeAssistant) -> None:
    """Test ColorTemperatureController reports color temp correctly."""
    hass.states.async_set(
        "light.test_on",
        "on",
        {
            "friendly_name": "Test light On",
            "color_temp": 240,
            "supported_color_modes": ["color_temp"],
        },
    )
    hass.states.async_set(
        "light.test_off",
        "off",
        {"friendly_name": "Test light Off", "supported_color_modes": ["color_temp"]},
    )

    properties = await reported_properties(hass, "light.test_on")
    properties.assert_equal(
        "Alexa.ColorTemperatureController", "colorTemperatureInKelvin", 4166
    )

    properties = await reported_properties(hass, "light.test_off")
    properties.assert_not_has_property(
        "Alexa.ColorTemperatureController", "colorTemperatureInKelvin"
    )


async def test_report_fan_speed_state(hass: HomeAssistant) -> None:
    """Test PercentageController, PowerLevelController reports fan speed correctly."""
    hass.states.async_set(
        "fan.off",
        "off",
        {
            "friendly_name": "Off fan",
            "supported_features": 1,
            "percentage": 0,
        },
    )
    hass.states.async_set(
        "fan.low_speed",
        "on",
        {
            "friendly_name": "Low speed fan",
            "supported_features": 1,
            "percentage": 33,
        },
    )
    hass.states.async_set(
        "fan.medium_speed",
        "on",
        {
            "friendly_name": "Medium speed fan",
            "supported_features": 1,
            "percentage": 66,
        },
    )
    hass.states.async_set(
        "fan.high_speed",
        "on",
        {
            "friendly_name": "High speed fan",
            "supported_features": 1,
            "percentage": 100,
        },
    )
    hass.states.async_set(
        "fan.speed_less_on",
        "on",
        {
            "friendly_name": "Speedless fan on",
            "supported_features": 0,
        },
    )
    hass.states.async_set(
        "fan.speed_less_off",
        "off",
        {
            "friendly_name": "Speedless fan off",
            "supported_features": 0,
        },
    )
    properties = await reported_properties(hass, "fan.off")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 0)

    properties = await reported_properties(hass, "fan.low_speed")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 33)

    properties = await reported_properties(hass, "fan.medium_speed")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 66)

    properties = await reported_properties(hass, "fan.high_speed")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 100)

    properties = await reported_properties(hass, "fan.speed_less_on")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 100)

    properties = await reported_properties(hass, "fan.speed_less_off")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 0)


async def test_report_humidifier_humidity_state(hass: HomeAssistant) -> None:
    """Test PercentageController, PowerLevelController humidifier humidity reporting."""
    hass.states.async_set(
        "humidifier.dry",
        "on",
        {
            "friendly_name": "Humidifier dry",
            "supported_features": 0,
            "humidity": 25,
            "min_humidity": 20,
            "max_humidity": 90,
        },
    )
    hass.states.async_set(
        "humidifier.wet",
        "on",
        {
            "friendly_name": "Humidifier wet",
            "supported_features": 0,
            "humidity": 80,
            "min_humidity": 20,
            "max_humidity": 90,
        },
    )
    properties = await reported_properties(hass, "humidifier.dry")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 25)

    properties = await reported_properties(hass, "humidifier.wet")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 80)


async def test_report_humidifier_mode(hass: HomeAssistant) -> None:
    """Test ModeController reports humidifier mode correctly."""
    hass.states.async_set(
        "humidifier.auto",
        "on",
        {
            "friendly_name": "Humidifier auto",
            "supported_features": 1,
            "humidity": 50,
            "mode": "Auto",
            "available_modes": ["Auto", "Low", "Medium", "High"],
            "min_humidity": 20,
            "max_humidity": 90,
        },
    )
    properties = await reported_properties(hass, "humidifier.auto")
    properties.assert_equal("Alexa.ModeController", "mode", "mode.Auto")

    hass.states.async_set(
        "humidifier.medium",
        "on",
        {
            "friendly_name": "Humidifier auto",
            "supported_features": 1,
            "humidity": 60,
            "mode": "Medium",
            "available_modes": ["Auto", "Low", "Medium", "High"],
            "min_humidity": 20,
            "max_humidity": 90,
        },
    )
    properties = await reported_properties(hass, "humidifier.medium")
    properties.assert_equal("Alexa.ModeController", "mode", "mode.Medium")


async def test_report_fan_preset_mode(hass: HomeAssistant) -> None:
    """Test ModeController reports fan preset_mode correctly."""
    hass.states.async_set(
        "fan.preset_mode",
        "eco",
        {
            "friendly_name": "eco enabled fan",
            "supported_features": 8,
            "preset_mode": "eco",
            "preset_modes": ["eco", "smart", "whoosh"],
        },
    )
    properties = await reported_properties(hass, "fan.preset_mode")
    properties.assert_equal("Alexa.ModeController", "mode", "preset_mode.eco")

    hass.states.async_set(
        "fan.preset_mode",
        "smart",
        {
            "friendly_name": "smart enabled fan",
            "supported_features": 8,
            "preset_mode": "smart",
            "preset_modes": ["eco", "smart", "whoosh"],
        },
    )
    properties = await reported_properties(hass, "fan.preset_mode")
    properties.assert_equal("Alexa.ModeController", "mode", "preset_mode.smart")

    hass.states.async_set(
        "fan.preset_mode",
        "whoosh",
        {
            "friendly_name": "whoosh enabled fan",
            "supported_features": 8,
            "preset_mode": "whoosh",
            "preset_modes": ["eco", "smart", "whoosh"],
        },
    )
    properties = await reported_properties(hass, "fan.preset_mode")
    properties.assert_equal("Alexa.ModeController", "mode", "preset_mode.whoosh")

    hass.states.async_set(
        "fan.preset_mode",
        "whoosh",
        {
            "friendly_name": "one preset mode fan",
            "supported_features": 8,
            "preset_mode": "auto",
            "preset_modes": ["auto"],
        },
    )
    properties = await reported_properties(hass, "fan.preset_mode")


async def test_report_fan_oscillating(hass: HomeAssistant) -> None:
    """Test ToggleController reports fan oscillating correctly."""
    hass.states.async_set(
        "fan.oscillating_off",
        "off",
        {"friendly_name": "fan oscillating off", "supported_features": 2},
    )
    hass.states.async_set(
        "fan.oscillating_on",
        "on",
        {
            "friendly_name": "Fan oscillating on",
            "oscillating": True,
            "supported_features": 2,
        },
    )

    properties = await reported_properties(hass, "fan.oscillating_off")
    properties.assert_equal("Alexa.ToggleController", "toggleState", "OFF")

    properties = await reported_properties(hass, "fan.oscillating_on")
    properties.assert_equal("Alexa.ToggleController", "toggleState", "ON")


async def test_report_fan_direction(hass: HomeAssistant) -> None:
    """Test ModeController reports fan direction correctly."""
    hass.states.async_set(
        "fan.off", "off", {"friendly_name": "Off fan", "supported_features": 4}
    )
    hass.states.async_set(
        "fan.reverse",
        "on",
        {
            "friendly_name": "Fan Reverse",
            "direction": "reverse",
            "supported_features": 4,
        },
    )
    hass.states.async_set(
        "fan.forward",
        "on",
        {
            "friendly_name": "Fan Forward",
            "direction": "forward",
            "supported_features": 4,
        },
    )

    properties = await reported_properties(hass, "fan.off")
    properties.assert_not_has_property("Alexa.ModeController", "mode")

    properties = await reported_properties(hass, "fan.reverse")
    properties.assert_equal("Alexa.ModeController", "mode", "direction.reverse")

    properties = await reported_properties(hass, "fan.forward")
    properties.assert_equal("Alexa.ModeController", "mode", "direction.forward")


async def test_report_remote_power(hass: HomeAssistant) -> None:
    """Test ModeController reports remote power state correctly."""
    hass.states.async_set(
        "remote.off",
        "off",
        {"current_activity": "TV", "activity_list": ["TV", "MUSIC", "DVD"]},
    )
    hass.states.async_set(
        "remote.on",
        "on",
        {"current_activity": "TV", "activity_list": ["TV", "MUSIC", "DVD"]},
    )

    properties = await reported_properties(hass, "remote#off")
    properties.assert_equal("Alexa.PowerController", "powerState", "OFF")

    properties = await reported_properties(hass, "remote#on")
    properties.assert_equal("Alexa.PowerController", "powerState", "ON")


async def test_report_remote_activity(hass: HomeAssistant) -> None:
    """Test ModeController reports remote activity correctly."""
    hass.states.async_set(
        "remote.unknown",
        "on",
        {
            "current_activity": "UNKNOWN",
            "supported_features": 4,
        },
    )
    hass.states.async_set(
        "remote.tv",
        "on",
        {
            "current_activity": "TV",
            "activity_list": ["TV", "MUSIC", "DVD"],
            "supported_features": 4,
        },
    )
    hass.states.async_set(
        "remote.music",
        "on",
        {
            "current_activity": "MUSIC",
            "activity_list": ["TV", "MUSIC", "DVD"],
            "supported_features": 4,
        },
    )
    hass.states.async_set(
        "remote.dvd",
        "on",
        {
            "current_activity": "DVD",
            "activity_list": ["TV", "MUSIC", "DVD"],
            "supported_features": 4,
        },
    )

    properties = await reported_properties(hass, "remote#unknown")
    properties.assert_not_has_property("Alexa.ModeController", "mode")

    properties = await reported_properties(hass, "remote#tv")
    properties.assert_equal("Alexa.ModeController", "mode", "activity.TV")

    properties = await reported_properties(hass, "remote#music")
    properties.assert_equal("Alexa.ModeController", "mode", "activity.MUSIC")

    properties = await reported_properties(hass, "remote#dvd")
    properties.assert_equal("Alexa.ModeController", "mode", "activity.DVD")


async def test_report_cover_range_value(hass: HomeAssistant) -> None:
    """Test RangeController reports cover position correctly."""
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
    properties.assert_equal("Alexa.RangeController", "rangeValue", 100)

    properties = await reported_properties(hass, "cover.half_open")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 50)

    properties = await reported_properties(hass, "cover.closed")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 0)


async def test_report_valve_range_value(hass: HomeAssistant) -> None:
    """Test RangeController reports valve position correctly."""
    all_valve_features = (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.STOP
        | ValveEntityFeature.SET_POSITION
    )
    hass.states.async_set(
        "valve.fully_open",
        "open",
        {
            "friendly_name": "Fully open valve",
            "current_position": 100,
            "supported_features": all_valve_features,
        },
    )
    hass.states.async_set(
        "valve.half_open",
        "open",
        {
            "friendly_name": "Half open valve",
            "current_position": 50,
            "supported_features": all_valve_features,
        },
    )
    hass.states.async_set(
        "valve.closed",
        "closed",
        {
            "friendly_name": "Closed valve",
            "current_position": 0,
            "supported_features": all_valve_features,
        },
    )

    properties = await reported_properties(hass, "valve.fully_open")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 100)

    properties = await reported_properties(hass, "valve.half_open")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 50)

    properties = await reported_properties(hass, "valve.closed")
    properties.assert_equal("Alexa.RangeController", "rangeValue", 0)


@pytest.mark.parametrize(
    (
        "supported_features",
        "has_mode_controller",
        "has_range_controller",
        "has_toggle_controller",
    ),
    [
        (ValveEntityFeature(0), False, False, False),
        (
            ValveEntityFeature.OPEN
            | ValveEntityFeature.CLOSE
            | ValveEntityFeature.STOP,
            True,
            False,
            True,
        ),
        (
            ValveEntityFeature.OPEN,
            True,
            False,
            False,
        ),
        (
            ValveEntityFeature.CLOSE,
            True,
            False,
            False,
        ),
        (
            ValveEntityFeature.STOP,
            False,
            False,
            True,
        ),
        (
            ValveEntityFeature.SET_POSITION,
            False,
            True,
            False,
        ),
        (
            ValveEntityFeature.STOP | ValveEntityFeature.SET_POSITION,
            False,
            True,
            True,
        ),
        (
            ValveEntityFeature.OPEN
            | ValveEntityFeature.CLOSE
            | ValveEntityFeature.SET_POSITION,
            False,
            True,
            False,
        ),
    ],
)
async def test_report_valve_controllers(
    hass: HomeAssistant,
    supported_features: ValveEntityFeature,
    has_mode_controller: bool,
    has_range_controller: bool,
    has_toggle_controller: bool,
) -> None:
    """Test valve controllers are reported correctly."""
    hass.states.async_set(
        "valve.custom",
        "opening",
        {
            "friendly_name": "Custom valve",
            "current_position": 0,
            "supported_features": supported_features,
        },
    )

    properties = await reported_properties(hass, "valve.custom")

    if has_mode_controller:
        properties.assert_equal("Alexa.ModeController", "mode", "state.opening")
    else:
        properties.assert_not_has_property("Alexa.ModeController", "mode")
    if has_range_controller:
        properties.assert_equal("Alexa.RangeController", "rangeValue", 0)
    else:
        properties.assert_not_has_property("Alexa.RangeController", "rangeValue")
    if has_toggle_controller:
        properties.assert_equal("Alexa.ToggleController", "toggleState", "OFF")
    else:
        properties.assert_not_has_property("Alexa.ToggleController", "toggleState")


async def test_report_climate_state(hass: HomeAssistant) -> None:
    """Test ThermostatController reports state correctly."""
    for auto_modes in (HVACMode.AUTO, HVACMode.HEAT_COOL):
        hass.states.async_set(
            "climate.downstairs",
            auto_modes,
            {
                "friendly_name": "Climate Downstairs",
                "supported_features": 91,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        )
        properties = await reported_properties(hass, "climate.downstairs")
        properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "AUTO")
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )

    for off_modes in (HVACMode.OFF,):
        hass.states.async_set(
            "climate.downstairs",
            off_modes,
            {
                "friendly_name": "Climate Downstairs",
                "supported_features": 91,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        )
        properties = await reported_properties(hass, "climate.downstairs")
        properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "OFF")
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )

    # assert dry is reported as CUSTOM
    hass.states.async_set(
        "climate.downstairs",
        "dry",
        {
            "friendly_name": "Climate Downstairs",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    properties = await reported_properties(hass, "climate.downstairs")
    properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "CUSTOM")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )

    # assert fan_only is reported as CUSTOM
    hass.states.async_set(
        "climate.downstairs",
        "fan_only",
        {
            "friendly_name": "Climate Downstairs",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 31,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    properties = await reported_properties(hass, "climate.downstairs")
    properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "CUSTOM")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 31.0, "scale": "CELSIUS"}
    )

    hass.states.async_set(
        "climate.heat",
        "heat",
        {
            "friendly_name": "Climate Heat",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    properties = await reported_properties(hass, "climate.heat")
    properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "HEAT")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )

    hass.states.async_set(
        "climate.cool",
        "cool",
        {
            "friendly_name": "Climate Cool",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    properties = await reported_properties(hass, "climate.cool")
    properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "COOL")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )

    for state in "unavailable", "unknown":
        hass.states.async_set(
            f"climate.{state}",
            state,
            {"friendly_name": f"Climate {state}", "supported_features": 91},
        )
        properties = await reported_properties(hass, f"climate.{state}")
        properties.assert_not_has_property(
            "Alexa.ThermostatController", "thermostatMode"
        )

    hass.states.async_set(
        "climate.unsupported",
        "blablabla",
        {
            "friendly_name": "Climate Unsupported",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    msg = await reported_properties(hass, "climate.unsupported", True)
    assert msg["event"]["header"]["name"] == "ErrorResponse"
    assert msg["event"]["payload"]["type"] == "INTERNAL_ERROR"


async def test_report_on_off_climate_state(hass: HomeAssistant) -> None:
    """Test ThermostatController with on/off features reports state correctly."""
    on_off_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    for auto_modes in (HVACMode.HEAT,):
        hass.states.async_set(
            "climate.onoff",
            auto_modes,
            {
                "friendly_name": "Climate Downstairs",
                "supported_features": on_off_features,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        )
        properties = await reported_properties(hass, "climate.onoff")
        properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "HEAT")
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )

    for off_modes in (HVACMode.OFF,):
        hass.states.async_set(
            "climate.onoff",
            off_modes,
            {
                "friendly_name": "Climate Downstairs",
                "supported_features": on_off_features,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        )
        properties = await reported_properties(hass, "climate.onoff")
        properties.assert_equal("Alexa.ThermostatController", "thermostatMode", "OFF")
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )


async def test_report_water_heater_state(hass: HomeAssistant) -> None:
    """Test ThermostatController also reports state correctly for water heaters."""
    for operation_mode in (STATE_ECO, STATE_GAS, STATE_HEAT_PUMP):
        hass.states.async_set(
            "water_heater.boyler",
            operation_mode,
            {
                "friendly_name": "Boyler",
                "supported_features": 11,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
                ATTR_OPERATION_LIST: [STATE_ECO, STATE_GAS, STATE_HEAT_PUMP],
                ATTR_OPERATION_MODE: operation_mode,
            },
        )
        properties = await reported_properties(hass, "water_heater.boyler")
        properties.assert_not_has_property(
            "Alexa.ThermostatController", "thermostatMode"
        )
        properties.assert_equal(
            "Alexa.ModeController", "mode", f"operation_mode.{operation_mode}"
        )
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )

    for off_mode in (STATE_OFF,):
        hass.states.async_set(
            "water_heater.boyler",
            off_mode,
            {
                "friendly_name": "Boyler",
                "supported_features": 11,
                ATTR_CURRENT_TEMPERATURE: 34,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        )
        properties = await reported_properties(hass, "water_heater.boyler")
        properties.assert_not_has_property(
            "Alexa.ThermostatController", "thermostatMode"
        )
        properties.assert_not_has_property("Alexa.ModeController", "mode")
        properties.assert_equal(
            "Alexa.TemperatureSensor",
            "temperature",
            {"value": 34.0, "scale": "CELSIUS"},
        )

    for state in "unavailable", "unknown":
        hass.states.async_set(
            f"water_heater.{state}",
            state,
            {"friendly_name": f"Boyler {state}", "supported_features": 11},
        )
        properties = await reported_properties(hass, f"water_heater.{state}")
        properties.assert_not_has_property(
            "Alexa.ThermostatController", "thermostatMode"
        )
        properties.assert_not_has_property("Alexa.ModeController", "mode")


async def test_report_singe_mode_water_heater(hass: HomeAssistant) -> None:
    """Test ThermostatController also reports state correctly for water heaters."""
    operation_mode = STATE_ECO
    hass.states.async_set(
        "water_heater.boyler",
        operation_mode,
        {
            "friendly_name": "Boyler",
            "supported_features": 11,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_OPERATION_LIST: [STATE_ECO],
            ATTR_OPERATION_MODE: operation_mode,
        },
    )
    properties = await reported_properties(hass, "water_heater.boyler")
    properties.assert_not_has_property("Alexa.ThermostatController", "thermostatMode")
    properties.assert_equal(
        "Alexa.ModeController", "mode", f"operation_mode.{operation_mode}"
    )
    properties.assert_equal(
        "Alexa.TemperatureSensor",
        "temperature",
        {"value": 34.0, "scale": "CELSIUS"},
    )


async def test_temperature_sensor_sensor(hass: HomeAssistant) -> None:
    """Test TemperatureSensor reports sensor temperature correctly."""
    for bad_value in (STATE_UNKNOWN, STATE_UNAVAILABLE, "not-number"):
        hass.states.async_set(
            "sensor.temp_living_room",
            bad_value,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )

        properties = await reported_properties(hass, "sensor.temp_living_room")
        properties.assert_not_has_property("Alexa.TemperatureSensor", "temperature")

    hass.states.async_set(
        "sensor.temp_living_room",
        "34",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    properties = await reported_properties(hass, "sensor.temp_living_room")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )


async def test_temperature_sensor_climate(hass: HomeAssistant) -> None:
    """Test TemperatureSensor reports climate temperature correctly."""
    for bad_value in (STATE_UNKNOWN, STATE_UNAVAILABLE, "not-number"):
        hass.states.async_set(
            "climate.downstairs",
            HVACMode.HEAT,
            {ATTR_CURRENT_TEMPERATURE: bad_value},
        )

        properties = await reported_properties(hass, "climate.downstairs")
        properties.assert_not_has_property("Alexa.TemperatureSensor", "temperature")

    hass.states.async_set(
        "climate.downstairs",
        HVACMode.HEAT,
        {ATTR_CURRENT_TEMPERATURE: 34},
    )
    properties = await reported_properties(hass, "climate.downstairs")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )


async def test_temperature_sensor_water_heater(hass: HomeAssistant) -> None:
    """Test TemperatureSensor reports climate temperature correctly."""
    for bad_value in (STATE_UNKNOWN, STATE_UNAVAILABLE, "not-number"):
        hass.states.async_set(
            "water_heater.boyler",
            STATE_ECO,
            {"supported_features": 11, ATTR_CURRENT_TEMPERATURE: bad_value},
        )

        properties = await reported_properties(hass, "water_heater.boyler")
        properties.assert_not_has_property("Alexa.TemperatureSensor", "temperature")

    hass.states.async_set(
        "water_heater.boyler",
        STATE_ECO,
        {"supported_features": 11, ATTR_CURRENT_TEMPERATURE: 34},
    )
    properties = await reported_properties(hass, "water_heater.boyler")
    properties.assert_equal(
        "Alexa.TemperatureSensor", "temperature", {"value": 34.0, "scale": "CELSIUS"}
    )


async def test_report_alarm_control_panel_state(hass: HomeAssistant) -> None:
    """Test SecurityPanelController implements armState property."""
    hass.states.async_set(
        "alarm_control_panel.armed_away", AlarmControlPanelState.ARMED_AWAY, {}
    )
    hass.states.async_set(
        "alarm_control_panel.armed_custom_bypass",
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.armed_home", AlarmControlPanelState.ARMED_HOME, {}
    )
    hass.states.async_set(
        "alarm_control_panel.armed_night", AlarmControlPanelState.ARMED_NIGHT, {}
    )
    hass.states.async_set(
        "alarm_control_panel.disarmed", AlarmControlPanelState.DISARMED, {}
    )

    properties = await reported_properties(hass, "alarm_control_panel.armed_away")
    properties.assert_equal("Alexa.SecurityPanelController", "armState", "ARMED_AWAY")

    properties = await reported_properties(
        hass, "alarm_control_panel.armed_custom_bypass"
    )
    properties.assert_equal("Alexa.SecurityPanelController", "armState", "ARMED_STAY")

    properties = await reported_properties(hass, "alarm_control_panel.armed_home")
    properties.assert_equal("Alexa.SecurityPanelController", "armState", "ARMED_STAY")

    properties = await reported_properties(hass, "alarm_control_panel.armed_night")
    properties.assert_equal("Alexa.SecurityPanelController", "armState", "ARMED_NIGHT")

    properties = await reported_properties(hass, "alarm_control_panel.disarmed")
    properties.assert_equal("Alexa.SecurityPanelController", "armState", "DISARMED")


async def test_report_playback_state(hass: HomeAssistant) -> None:
    """Test PlaybackStateReporter implements playbackState property."""
    hass.states.async_set(
        "media_player.test",
        "off",
        {
            "friendly_name": "Test media player",
            "supported_features": MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP,
            "volume_level": 0.75,
            "source_list": [None],
        },
    )

    properties = await reported_properties(hass, "media_player.test")

    properties.assert_equal(
        "Alexa.PlaybackStateReporter", "playbackState", {"state": "STOPPED"}
    )


async def test_report_speaker_volume(hass: HomeAssistant) -> None:
    """Test Speaker reports volume correctly."""
    hass.states.async_set(
        "media_player.test_speaker",
        "on",
        {
            "friendly_name": "Test media player speaker",
            "supported_features": MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET,
            "volume_level": None,
            "device_class": "speaker",
        },
    )
    properties = await reported_properties(hass, "media_player.test_speaker")
    properties.assert_not_has_property("Alexa.Speaker", "volume")

    for good_value in range(101):
        hass.states.async_set(
            "media_player.test_speaker",
            "on",
            {
                "friendly_name": "Test media player speaker",
                "supported_features": MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_SET,
                "volume_level": good_value / 100,
                "device_class": "speaker",
            },
        )
        properties = await reported_properties(hass, "media_player.test_speaker")
        properties.assert_equal("Alexa.Speaker", "volume", good_value)


async def test_report_image_processing(hass: HomeAssistant) -> None:
    """Test EventDetectionSensor implements humanPresenceDetectionState property."""
    hass.states.async_set(
        "image_processing.test_face",
        0,
        {
            "friendly_name": "Test face",
            "device_class": "face",
            "faces": [],
            "total_faces": 0,
        },
    )

    properties = await reported_properties(hass, "image_processing#test_face")
    properties.assert_equal(
        "Alexa.EventDetectionSensor",
        "humanPresenceDetectionState",
        {"value": "NOT_DETECTED"},
    )

    hass.states.async_set(
        "image_processing.test_classifier",
        3,
        {
            "friendly_name": "Test classifier",
            "device_class": "face",
            "faces": [
                {"confidence": 98.34, "name": "Hans", "age": 16.0, "gender": "male"},
                {"name": "Helena", "age": 28.0, "gender": "female"},
                {"confidence": 62.53, "name": "Luna"},
            ],
            "total_faces": 3,
        },
    )
    properties = await reported_properties(hass, "image_processing#test_classifier")
    properties.assert_equal(
        "Alexa.EventDetectionSensor",
        "humanPresenceDetectionState",
        {"value": "DETECTED"},
    )


@pytest.mark.parametrize("domain", ["button", "input_button"])
async def test_report_button_pressed(hass: HomeAssistant, domain: str) -> None:
    """Test button presses report human presence detection events.

    For use to trigger routines.
    """
    hass.states.async_set(
        f"{domain}.test_button", "now", {"friendly_name": "Test button"}
    )

    properties = await reported_properties(hass, f"{domain}#test_button")
    properties.assert_equal(
        "Alexa.EventDetectionSensor",
        "humanPresenceDetectionState",
        {"value": "DETECTED"},
    )


@pytest.mark.parametrize("domain", ["switch", "input_boolean"])
async def test_toggle_entities_report_contact_events(
    hass: HomeAssistant, domain: str
) -> None:
    """Test toggles and switches report contact sensor events to trigger routines."""
    hass.states.async_set(
        f"{domain}.test_toggle", "on", {"friendly_name": "Test toggle"}
    )

    properties = await reported_properties(hass, f"{domain}#test_toggle")
    properties.assert_equal(
        "Alexa.PowerController",
        "powerState",
        "ON",
    )
    properties.assert_equal(
        "Alexa.ContactSensor",
        "detectionState",
        "DETECTED",
    )

    hass.states.async_set(
        f"{domain}.test_toggle", "off", {"friendly_name": "Test toggle"}
    )

    properties = await reported_properties(hass, f"{domain}#test_toggle")
    properties.assert_equal(
        "Alexa.PowerController",
        "powerState",
        "OFF",
    )
    properties.assert_equal(
        "Alexa.ContactSensor",
        "detectionState",
        "NOT_DETECTED",
    )


async def test_get_property_blowup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle a property blowing up."""
    hass.states.async_set(
        "climate.downstairs",
        HVACMode.AUTO,
        {
            "friendly_name": "Climate Downstairs",
            "supported_features": 91,
            ATTR_CURRENT_TEMPERATURE: 34,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    with patch(
        "homeassistant.components.alexa.capabilities.float",
        side_effect=Exception("Boom Fail"),
    ):
        properties = await reported_properties(hass, "climate.downstairs")
        properties.assert_not_has_property("Alexa.ThermostatController", "temperature")

    assert "Boom Fail" in caplog.text
