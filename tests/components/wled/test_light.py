"""Tests for the WLED light platform."""
import json
from unittest.mock import MagicMock

import pytest
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.wled.const import CONF_KEEP_MASTER_LIGHT, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_rgb_light_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the creation and values of the WLED lights."""
    # First segment of the strip
    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Solid"
    assert state.attributes.get(ATTR_HS_COLOR) == (37.412, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get("light.wled_rgb_light"))
    assert entry.unique_id == "aabbccddeeff_0"

    # Second segment of the strip
    assert (state := hass.states.get("light.wled_rgb_light_segment_1"))
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Blink"
    assert state.attributes.get(ATTR_HS_COLOR) == (148.941, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get("light.wled_rgb_light_segment_1"))
    assert entry.unique_id == "aabbccddeeff_1"

    # Test main control of the lightstrip
    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get("light.wled_rgb_light_main"))
    assert entry.unique_id == "aabbccddeeff"


async def test_segment_change_state(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the change of state of the WLED segments."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_TRANSITION: 5},
        blocking=True,
    )
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        on=False,
        segment_id=0,
        transition=50,
    )

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
    assert mock_wled.segment.call_count == 2
    mock_wled.segment.assert_called_with(
        brightness=42,
        color_primary=(255, 0, 0),
        effect="Chase",
        on=True,
        segment_id=0,
        transition=50,
    )


async def test_main_change_state(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the change of state of the WLED main light control."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light_main", ATTR_TRANSITION: 5},
        blocking=True,
    )
    assert mock_wled.master.call_count == 1
    mock_wled.master.assert_called_with(
        on=False,
        transition=50,
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_BRIGHTNESS: 42,
            ATTR_ENTITY_ID: "light.wled_rgb_light_main",
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    assert mock_wled.master.call_count == 2
    mock_wled.master.assert_called_with(
        brightness=42,
        on=True,
        transition=50,
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light_main", ATTR_TRANSITION: 5},
        blocking=True,
    )
    assert mock_wled.master.call_count == 3
    mock_wled.master.assert_called_with(
        on=False,
        transition=50,
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_BRIGHTNESS: 42,
            ATTR_ENTITY_ID: "light.wled_rgb_light_main",
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    assert mock_wled.master.call_count == 4
    mock_wled.master.assert_called_with(
        brightness=42,
        on=True,
        transition=50,
    )


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_dynamically_handle_segments(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    assert (segment0 := hass.states.get("light.wled_rgb_light"))
    assert segment0.state == STATE_ON
    assert not hass.states.get("light.wled_rgb_light_main")
    assert not hass.states.get("light.wled_rgb_light_segment_1")

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert (main := hass.states.get("light.wled_rgb_light_main"))
    assert main.state == STATE_ON
    assert (segment0 := hass.states.get("light.wled_rgb_light"))
    assert segment0.state == STATE_ON
    assert (segment1 := hass.states.get("light.wled_rgb_light_segment_1"))
    assert segment1.state == STATE_ON

    # Test adding if segment shows up again, including the main entity
    mock_wled.update.return_value = return_value
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert (main := hass.states.get("light.wled_rgb_light_main"))
    assert main.state == STATE_UNAVAILABLE
    assert (segment0 := hass.states.get("light.wled_rgb_light"))
    assert segment0.state == STATE_ON
    assert (segment1 := hass.states.get("light.wled_rgb_light_segment_1"))
    assert segment1.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_single_segment_behavior(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the behavior of the integration with a single segment."""
    device = mock_wled.update.return_value

    assert not hass.states.get("light.wled_rgb_light_main")
    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.state == STATE_ON

    # Test segment brightness takes main into account
    device.state.brightness = 100
    device.state.segments[0].brightness = 255
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.attributes.get(ATTR_BRIGHTNESS) == 100

    # Test segment is off when main is off
    device.state.on = False
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_OFF

    # Test main is turned off when turning off a single segment
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_TRANSITION: 5},
        blocking=True,
    )
    assert mock_wled.master.call_count == 1
    mock_wled.master.assert_called_with(
        on=False,
        transition=50,
    )

    # Test main is turned on when turning on a single segment, and segment
    # brightness is set to 255.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_TRANSITION: 5,
            ATTR_BRIGHTNESS: 42,
        },
        blocking=True,
    )
    assert mock_wled.segment.call_count == 1
    assert mock_wled.master.call_count == 2
    mock_wled.segment.assert_called_with(on=True, segment_id=0, brightness=255)
    mock_wled.master.assert_called_with(on=True, transition=50, brightness=42)


async def test_light_error(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test error handling of the WLED lights."""
    mock_wled.segment.side_effect = WLEDError

    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.wled_rgb_light"},
            blocking=True,
        )

    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.state == STATE_ON
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(on=False, segment_id=0, transition=None)


async def test_light_connection_error(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test error handling of the WLED switches."""
    mock_wled.segment.side_effect = WLEDConnectionError

    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.wled_rgb_light"},
            blocking=True,
        )

    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.state == STATE_UNAVAILABLE
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(on=False, segment_id=0, transition=None)


@pytest.mark.parametrize("device_fixture", ["rgbw"])
async def test_rgbw_light(hass: HomeAssistant, mock_wled: MagicMock) -> None:
    """Test RGBW support for WLED."""
    assert (state := hass.states.get("light.wled_rgbw_light"))
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_RGBW_COLOR) == (255, 0, 0, 139)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.wled_rgbw_light",
            ATTR_RGBW_COLOR: (255, 255, 255, 255),
        },
        blocking=True,
    )
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        color_primary=(255, 255, 255, 255),
        on=True,
        segment_id=0,
    )


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_single_segment_with_keep_main_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the behavior of the integration with a single segment."""
    assert not hass.states.get("light.wled_rgb_light_main")

    hass.config_entries.async_update_entry(
        init_integration, options={CONF_KEEP_MASTER_LIGHT: True}
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.state == STATE_ON
