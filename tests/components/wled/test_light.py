"""Tests for the WLED light platform."""
import aiohttp
from asynctest.mock import patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.wled.const import (
    ATTR_INTENSITY,
    ATTR_PALETTE,
    ATTR_PLAYLIST,
    ATTR_PRESET,
    ATTR_SPEED,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_rgb_light_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the WLED lights."""
    await init_integration(hass, aioclient_mock)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # First segment of the strip
    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Solid"
    assert state.attributes.get(ATTR_HS_COLOR) == (37.412, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.attributes.get(ATTR_INTENSITY) == 128
    assert state.attributes.get(ATTR_PALETTE) == "Default"
    assert state.attributes.get(ATTR_PLAYLIST) is None
    assert state.attributes.get(ATTR_PRESET) is None
    assert state.attributes.get(ATTR_SPEED) == 32
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.wled_rgb_light")
    assert entry
    assert entry.unique_id == "aabbccddeeff_0"

    # Second segment of the strip
    state = hass.states.get("light.wled_rgb_light_1")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Blink"
    assert state.attributes.get(ATTR_HS_COLOR) == (148.941, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.attributes.get(ATTR_INTENSITY) == 64
    assert state.attributes.get(ATTR_PALETTE) == "Random Cycle"
    assert state.attributes.get(ATTR_PLAYLIST) is None
    assert state.attributes.get(ATTR_PRESET) is None
    assert state.attributes.get(ATTR_SPEED) == 16
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.wled_rgb_light_1")
    assert entry
    assert entry.unique_id == "aabbccddeeff_1"


async def test_switch_change_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the change of state of the WLED switches."""
    await init_integration(hass, aioclient_mock)

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_TRANSITION: 5},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            on=False, segment_id=0, transition=50,
        )

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_BRIGHTNESS: 42,
                ATTR_EFFECT: "Chase",
                ATTR_ENTITY_ID: "light.wled_rgb_light",
                ATTR_RGB_COLOR: [255, 0, 0],
                ATTR_TRANSITION: 5,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            brightness=42,
            color_primary=(255, 0, 0),
            effect="Chase",
            on=True,
            segment_id=0,
            transition=50,
        )

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_COLOR_TEMP: 400},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            color_primary=(255, 159, 70), on=True, segment_id=0,
        )


async def test_light_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the WLED switches."""
    aioclient_mock.post("http://example.local:80/json/state", exc=aiohttp.ClientError)
    entry = await init_integration(hass, aioclient_mock)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    with patch("homeassistant.components.wled.WLEDDataUpdateCoordinator.async_refresh"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.wled_rgb_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert not coordinator.last_update_success


async def test_rgbw_light(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test RGBW support for WLED."""
    await init_integration(hass, aioclient_mock, rgbw=True)

    state = hass.states.get("light.wled_rgbw_light")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_HS_COLOR) == (0.0, 100.0)
    assert state.attributes.get(ATTR_WHITE_VALUE) == 139

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.wled_rgbw_light", ATTR_COLOR_TEMP: 400},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            on=True, segment_id=0, color_primary=(255, 159, 70, 139),
        )

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.wled_rgbw_light", ATTR_WHITE_VALUE: 100},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            color_primary=(255, 0, 0, 100), on=True, segment_id=0,
        )

    with patch("wled.WLED.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.wled_rgbw_light",
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_WHITE_VALUE: 100,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            color_primary=(0, 0, 0, 100), on=True, segment_id=0,
        )
