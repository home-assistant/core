"""Tests for the Abode light device."""

from unittest.mock import patch

from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

DEVICE_ID = "light.living_room_lamp"


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, LIGHT_DOMAIN)

    entry = entity_registry.async_get(DEVICE_ID)
    assert entry.unique_id == "741385f4388b2637df4c6b398fe50581"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the light attributes are correct."""
    await setup_platform(hass, LIGHT_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 204
    assert state.attributes.get(ATTR_RGB_COLOR) == (0, 63, 255)
    assert state.attributes.get(ATTR_COLOR_TEMP) is None
    assert state.attributes.get(ATTR_DEVICE_ID) == "ZB:db5b1a"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "RGB Dimmer"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Living Room Lamp"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.HS
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the light can be turned off."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.switch_off") as mock_switch_off:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_switch_off.assert_called_once()


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the light can be turned on."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.switch_on") as mock_switch_on:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_switch_on.assert_called_once()


async def test_set_brightness(hass: HomeAssistant) -> None:
    """Test the brightness can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.set_level") as mock_set_level:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "brightness": 100},
            blocking=True,
        )
        await hass.async_block_till_done()
        # Brightness is converted in abode.light.AbodeLight.turn_on
        mock_set_level.assert_called_once_with(39)


async def test_set_color(hass: HomeAssistant) -> None:
    """Test the color can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.set_color") as mock_set_color:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "hs_color": [240, 100]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_color.assert_called_once_with((240.0, 100.0))


async def test_set_color_temp(hass: HomeAssistant) -> None:
    """Test the color temp can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch(
        "jaraco.abode.devices.light.Light.set_color_temp"
    ) as mock_set_color_temp:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "color_temp": 309},
            blocking=True,
        )
        await hass.async_block_till_done()
        # Color temp is converted in abode.light.AbodeLight.turn_on
        mock_set_color_temp.assert_called_once_with(3236)
