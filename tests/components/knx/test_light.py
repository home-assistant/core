"""Test knx light."""

from homeassistant.components.knx import KNX_ADDRESS, SupportedPlatforms
from homeassistant.components.knx.schema import LightSchema
from homeassistant.const import CONF_NAME

from . import setup_knx_integration

from tests.components.knx.conftest import KNXIPMock


async def test_light_brightness(hass, knx_ip_interface_mock: KNXIPMock):
    """Test that a turn_on with unsupported attribute turns a light on."""
    name_onoff = "knx_no_brightness"
    name_brightness = "knx_with_brightness"
    name_color = "knx_with_color"
    name_white = "knx_with_white"
    name_colortemp = "knx_with_colortemp"
    entity_onoff = "light." + name_onoff
    entity_brightness = "light." + name_brightness
    entity_color = "light." + name_color
    entity_white = "light." + name_white
    entity_colortemp = "light." + name_colortemp
    ga_onoff = "1/1/8"
    ga_brightness = "1/1/10"
    ga_color = "1/1/12"
    ga_white_onoff = "1/1/13"
    ga_white = "1/1/14"
    ga_colortemp = "1/1/16"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            SupportedPlatforms.LIGHT.value: [
                {
                    CONF_NAME: name_onoff,
                    KNX_ADDRESS: ga_onoff,
                },
                {
                    CONF_NAME: name_brightness,
                    KNX_ADDRESS: "1/1/9",
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: ga_brightness,
                },
                {
                    CONF_NAME: name_color,
                    KNX_ADDRESS: "1/1/11",
                    LightSchema.CONF_COLOR_ADDRESS: ga_color,
                },
                {
                    CONF_NAME: name_white,
                    KNX_ADDRESS: ga_white_onoff,
                    LightSchema.CONF_RGBW_ADDRESS: ga_white,
                },
                {
                    CONF_NAME: name_colortemp,
                    KNX_ADDRESS: "1/1/15",
                    LightSchema.CONF_COLOR_TEMP_ADDRESS: ga_colortemp,
                },
            ]
        },
    )
    # check count of defined lights
    assert len(hass.states.async_all()) == 5

    # Turn on/off simple lamp
    knx_ip_interface_mock.reset_mock()
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_onoff}, blocking=True
    )
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_onoff}, blocking=True
    )
    knx_ip_interface_mock.assert_telegrams_gas([ga_onoff, ga_onoff], "switch on/off")

    for entity, attr, value, ga in [
        [entity_brightness, "brightness", 100, ga_brightness],
        [entity_color, "color_name", "blue", ga_color],
        [entity_white, "white_value", 88, ga_white],
        [entity_colortemp, "color_temp", 88, ga_colortemp],
    ]:
        # Turn on with specific attribute on lamp which supports specific attribute
        # Only the specific telegram is send; this implicitly switches the lamp on
        knx_ip_interface_mock.reset_mock()
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity, attr: value},
            blocking=True,
        )
        knx_ip_interface_mock.assert_telegrams_gas([ga], attr)

    for attr, value in [
        ["brightness", 100],
        ["color_name", "blue"],
        ["white_value", 88],
        ["color_temp", 88],
    ]:
        # Turn on with specific attribute on simple lamp
        knx_ip_interface_mock.reset_mock()
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_onoff, attr: value},
            blocking=True,
        )
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": entity_onoff}, blocking=True
        )
        assert knx_ip_interface_mock.send_telegram.call_count == 2, (
            "Expected telegrams for switch on/off while using " + attr
        )
        assert (
            str(
                knx_ip_interface_mock.send_telegram.call_args.args[
                    0
                ].destination_address
            )
            == ga_onoff
        ), ("Expected telegram for on/off address with attribute " + attr)


async def test_light_multi_change(hass, knx_ip_interface_mock: KNXIPMock):
    """Test that a change on an attribute changes only that attribute."""
    ga_onoff = "1/1/8"
    ga_onoff2 = "1/1/9"
    ga_brightness = "1/1/10"
    ga_color = "1/1/12"
    ga_white = "1/1/14"
    ga_colortemp = "1/1/16"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            SupportedPlatforms.LIGHT.value: [
                {
                    CONF_NAME: "lamp1",
                    KNX_ADDRESS: ga_onoff,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: ga_brightness,
                    LightSchema.CONF_COLOR_ADDRESS: ga_color,
                    LightSchema.CONF_COLOR_TEMP_ADDRESS: ga_colortemp,
                },
                {
                    CONF_NAME: "lamp2",
                    KNX_ADDRESS: ga_onoff2,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: ga_brightness,
                    LightSchema.CONF_RGBW_ADDRESS: ga_white,
                    LightSchema.CONF_COLOR_TEMP_ADDRESS: ga_colortemp,
                },
            ]
        },
    )
    # check count of defined lights
    assert len(hass.states.async_all()) == 2

    for lamp, ga_c in [["lamp1", ga_color], ["lamp2", ga_white]]:
        # Turn on lamp by setting color
        knx_ip_interface_mock.reset_mock()
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": f"light.{lamp}", "color_name": "blue"},
            blocking=True,
        )
        knx_ip_interface_mock.assert_telegrams_gas([ga_c], f"color for {lamp}")

        # Change brightness
        knx_ip_interface_mock.reset_mock()
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": f"light.{lamp}", "brightness": 88},
            blocking=True,
        )
        knx_ip_interface_mock.assert_telegrams_gas(
            [ga_brightness], f"brightness for {lamp}"
        )

    for attribute, value, ga in [
        ["color_name", "red", ga_color],
        ["color_temp", 77, ga_colortemp],
        ["brightness", 55, ga_brightness],
    ]:
        # Change attribute
        knx_ip_interface_mock.reset_mock()
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.lamp1", attribute: value},
            blocking=True,
        )
        knx_ip_interface_mock.assert_telegrams_gas([ga], attribute)
