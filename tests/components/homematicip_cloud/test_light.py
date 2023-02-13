"""Tests for HomematicIP Cloud light."""
from homematicip.base.enums import RGBColorState

from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_NAME,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .helper import async_manipulate_test_data, get_and_check_entity_basics


async def test_manually_configured_platform(hass: HomeAssistant) -> None:
    """Test that we do not set up an access point."""
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {"platform": HMIPC_DOMAIN}}
    )
    assert not hass.data.get(HMIPC_DOMAIN)


async def test_hmip_light(hass: HomeAssistant, default_mock_hap_factory) -> None:
    """Test HomematicipLight."""
    entity_id = "light.treppe_ch"
    entity_name = "Treppe CH"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    service_call_counter = len(hmip_device.mock_calls)
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "turn_off"
    assert hmip_device.mock_calls[-1][1] == ()

    await async_manipulate_test_data(hass, hmip_device, "on", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert ATTR_COLOR_MODE not in ha_state.attributes
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "turn_on"
    assert hmip_device.mock_calls[-1][1] == ()

    await async_manipulate_test_data(hass, hmip_device, "on", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_notification_light(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipNotificationLight."""
    entity_id = "light.alarm_status"
    entity_name = "Alarm Status"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    assert ATTR_COLOR_MODE not in ha_state.attributes
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION
    service_call_counter = len(hmip_device.mock_calls)

    # Send all color via service call.
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness_pct": "100", "transition": 100},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "set_rgb_dim_level_with_time"
    assert hmip_device.mock_calls[-1][2] == {
        "channelIndex": 2,
        "rgb": "RED",
        "dimLevel": 1.0,
        "onTime": 0,
        "rampTime": 100.0,
    }

    color_list = {
        RGBColorState.WHITE: [0.0, 0.0],
        RGBColorState.RED: [0.0, 100.0],
        RGBColorState.YELLOW: [60.0, 100.0],
        RGBColorState.GREEN: [120.0, 100.0],
        RGBColorState.TURQUOISE: [180.0, 100.0],
        RGBColorState.BLUE: [240.0, 100.0],
        RGBColorState.PURPLE: [300.0, 100.0],
    }

    for color, hs_color in color_list.items():
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id, "hs_color": hs_color},
            blocking=True,
        )
        assert hmip_device.mock_calls[-1][0] == "set_rgb_dim_level_with_time"
        assert hmip_device.mock_calls[-1][2] == {
            "channelIndex": 2,
            "dimLevel": 0.0392156862745098,
            "onTime": 0,
            "rampTime": 0.5,
            "rgb": color,
        }

    assert len(hmip_device.mock_calls) == service_call_counter + 8

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1, 2)
    await async_manipulate_test_data(
        hass, hmip_device, "simpleRGBColorState", RGBColorState.PURPLE, 2
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_COLOR_NAME] == RGBColorState.PURPLE
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id, "transition": 100}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 11
    assert hmip_device.mock_calls[-1][0] == "set_rgb_dim_level_with_time"
    assert hmip_device.mock_calls[-1][2] == {
        "channelIndex": 2,
        "dimLevel": 0.0,
        "onTime": 0,
        "rampTime": 100,
        "rgb": "PURPLE",
    }
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, 2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None, 2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)


async def test_hmip_dimmer(hass: HomeAssistant, default_mock_hap_factory) -> None:
    """Test HomematicipDimmer."""
    entity_id = "light.schlafzimmerlicht"
    entity_name = "Schlafzimmerlicht"
    device_model = "HmIP-BDT"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    assert ATTR_COLOR_MODE not in ha_state.attributes
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness_pct": "100"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 2
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1.0, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)


async def test_hmip_light_measuring(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipLightMeasuring."""
    entity_id = "light.flur_oben"
    entity_name = "Flur oben"
    device_model = "HmIP-BSM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    assert ATTR_COLOR_MODE not in ha_state.attributes
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "turn_on"
    assert hmip_device.mock_calls[-1][1] == ()
    await async_manipulate_test_data(hass, hmip_device, "on", True)
    await async_manipulate_test_data(hass, hmip_device, "currentPowerConsumption", 50)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "turn_off"
    assert hmip_device.mock_calls[-1][1] == ()
    await async_manipulate_test_data(hass, hmip_device, "on", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_wired_multi_dimmer(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipMultiDimmer."""
    entity_id = "light.raumlich_kuche"
    entity_name = "Raumlich (Küche)"
    device_model = "HmIPW-DRD3"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wired Dimmaktor – 3-fach (Küche)"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    assert ATTR_COLOR_MODE not in ha_state.attributes
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": "100"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 2
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0.39215686274509803, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)


async def test_hmip_din_rail_dimmer_3_channel1(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicIP DinRailDimmer3 Channel 1."""
    entity_id = "light.3_dimmer_channel1"
    entity_name = "3-Dimmer Channel1"
    device_model = "HmIP-DRDI3"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["3-Dimmer"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": "100"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 2
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0.39215686274509803, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0, 1)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None, channel=1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)


async def test_hmip_din_rail_dimmer_3_channel2(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicIP DinRailDimmer3 Channel 2."""
    entity_id = "light.3_dimmer_channel2"
    entity_name = "3-Dimmer Channel2"
    device_model = "HmIP-DRDI3"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["3-Dimmer"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1, 2)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": "100"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 2
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0.39215686274509803, 2)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1, channel=2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0, 2)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, channel=2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None, channel=2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)


async def test_hmip_din_rail_dimmer_3_channel3(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicIP DinRailDimmer3 Channel 3."""
    entity_id = "light.esstisch"
    entity_name = "Esstisch"
    device_model = "HmIP-DRDI3"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["3-Dimmer"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (1, 3)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": "100"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 2
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0.39215686274509803, 3)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 1, channel=3)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_BRIGHTNESS] == 255
    assert ha_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert ha_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 4
    assert hmip_device.mock_calls[-1][0] == "set_dim_level"
    assert hmip_device.mock_calls[-1][1] == (0, 3)
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, channel=3)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    await async_manipulate_test_data(hass, hmip_device, "dimLevel", None, channel=3)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_BRIGHTNESS)
