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
from homeassistant.components.wled.const import (
    ATTR_INTENSITY,
    ATTR_PALETTE,
    ATTR_PRESET,
    ATTR_REVERSE,
    ATTR_SPEED,
    CONF_KEEP_MASTER_LIGHT,
    DOMAIN,
    SCAN_INTERVAL,
    SERVICE_EFFECT,
    SERVICE_PRESET,
)
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
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_rgb_light_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the creation and values of the WLED lights."""
    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Solid"
    assert state.attributes.get(ATTR_HS_COLOR) == (37.412, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.attributes.get(ATTR_INTENSITY) == 128
    assert state.attributes.get(ATTR_PALETTE) == "Default"
    assert state.attributes.get(ATTR_PRESET) is None
    assert state.attributes.get(ATTR_REVERSE) is False
    assert state.attributes.get(ATTR_SPEED) == 32
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.wled_rgb_light")
    assert entry
    assert entry.unique_id == "aabbccddeeff_0"

    # Second segment of the strip
    state = hass.states.get("light.wled_rgb_light_segment_1")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.attributes.get(ATTR_EFFECT) == "Blink"
    assert state.attributes.get(ATTR_HS_COLOR) == (148.941, 100.0)
    assert state.attributes.get(ATTR_ICON) == "mdi:led-strip-variant"
    assert state.attributes.get(ATTR_INTENSITY) == 64
    assert state.attributes.get(ATTR_PALETTE) == "Random Cycle"
    assert state.attributes.get(ATTR_PRESET) is None
    assert state.attributes.get(ATTR_REVERSE) is True
    assert state.attributes.get(ATTR_SPEED) == 16
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.wled_rgb_light_segment_1")
    assert entry
    assert entry.unique_id == "aabbccddeeff_1"

    # Test master control of the lightstrip
    state = hass.states.get("light.wled_rgb_light_master")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 127
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.wled_rgb_light_master")
    assert entry
    assert entry.unique_id == "aabbccddeeff"


async def test_segment_change_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the change of state of the WLED segments."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_TRANSITION: 5},
        blocking=True,
    )
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 2
    mock_wled.segment.assert_called_with(
        brightness=42,
        color_primary=(255, 0, 0),
        effect="Chase",
        on=True,
        segment_id=0,
        transition=50,
    )


async def test_master_change_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the change of state of the WLED master light control."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light_master", ATTR_TRANSITION: 5},
        blocking=True,
    )
    await hass.async_block_till_done()
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
            ATTR_ENTITY_ID: "light.wled_rgb_light_master",
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.master.call_count == 2
    mock_wled.master.assert_called_with(
        brightness=42,
        on=True,
        transition=50,
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light_master", ATTR_TRANSITION: 5},
        blocking=True,
    )
    await hass.async_block_till_done()
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
            ATTR_ENTITY_ID: "light.wled_rgb_light_master",
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.master.call_count == 4
    mock_wled.master.assert_called_with(
        brightness=42,
        on=True,
        transition=50,
    )


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_dynamically_handle_segments(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    master = hass.states.get("light.wled_rgb_light_master")
    segment0 = hass.states.get("light.wled_rgb_light")
    segment1 = hass.states.get("light.wled_rgb_light_segment_1")
    assert segment0
    assert segment0.state == STATE_ON
    assert not master
    assert not segment1

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    master = hass.states.get("light.wled_rgb_light_master")
    segment0 = hass.states.get("light.wled_rgb_light")
    segment1 = hass.states.get("light.wled_rgb_light_segment_1")
    assert master
    assert master.state == STATE_ON
    assert segment0
    assert segment0.state == STATE_ON
    assert segment1
    assert segment1.state == STATE_ON

    # Test adding if segment shows up again, including the master entity
    mock_wled.update.return_value = return_value
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    master = hass.states.get("light.wled_rgb_light_master")
    segment0 = hass.states.get("light.wled_rgb_light")
    segment1 = hass.states.get("light.wled_rgb_light_segment_1")
    assert master
    assert master.state == STATE_UNAVAILABLE
    assert segment0
    assert segment0.state == STATE_ON
    assert segment1
    assert segment1.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_single_segment_behavior(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the behavior of the integration with a single segment."""
    device = mock_wled.update.return_value

    assert not hass.states.get("light.wled_rgb_light_master")
    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_ON

    # Test segment brightness takes master into account
    device.state.brightness = 100
    device.state.segments[0].brightness = 255
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 100

    # Test segment is off when master is off
    device.state.on = False
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_OFF

    # Test master is turned off when turning off a single segment
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_TRANSITION: 5},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.master.call_count == 1
    mock_wled.master.assert_called_with(
        on=False,
        transition=50,
    )

    # Test master is turned on when turning on a single segment, and segment
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
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    assert mock_wled.master.call_count == 2
    mock_wled.segment.assert_called_with(on=True, segment_id=0, brightness=255)
    mock_wled.master.assert_called_with(on=True, transition=50, brightness=42)


async def test_light_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED lights."""
    mock_wled.segment.side_effect = WLEDError

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_ON
    assert "Invalid response from API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(on=False, segment_id=0, transition=None)


async def test_light_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED switches."""
    mock_wled.segment.side_effect = WLEDConnectionError

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wled_rgb_light"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(on=False, segment_id=0, transition=None)


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_rgbw_light(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test RGBW support for WLED."""
    state = hass.states.get("light.wled_rgbw_light")
    assert state
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
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        color_primary=(255, 255, 255, 255),
        on=True,
        segment_id=0,
    )


async def test_effect_service(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the effect service of a WLED light."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {
            ATTR_EFFECT: "Rainbow",
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_INTENSITY: 200,
            ATTR_PALETTE: "Tiamat",
            ATTR_REVERSE: True,
            ATTR_SPEED: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        effect="Rainbow",
        intensity=200,
        palette="Tiamat",
        reverse=True,
        segment_id=0,
        speed=100,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_EFFECT: 9},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 2
    mock_wled.segment.assert_called_with(
        segment_id=0,
        effect=9,
        intensity=None,
        palette=None,
        reverse=None,
        speed=None,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_INTENSITY: 200,
            ATTR_REVERSE: True,
            ATTR_SPEED: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 3
    mock_wled.segment.assert_called_with(
        intensity=200,
        reverse=True,
        segment_id=0,
        speed=100,
        effect=None,
        palette=None,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {
            ATTR_EFFECT: "Rainbow",
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_PALETTE: "Tiamat",
            ATTR_REVERSE: True,
            ATTR_SPEED: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 4
    mock_wled.segment.assert_called_with(
        effect="Rainbow",
        palette="Tiamat",
        reverse=True,
        segment_id=0,
        speed=100,
        intensity=None,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {
            ATTR_EFFECT: "Rainbow",
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_INTENSITY: 200,
            ATTR_SPEED: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 5
    mock_wled.segment.assert_called_with(
        effect="Rainbow",
        intensity=200,
        segment_id=0,
        speed=100,
        palette=None,
        reverse=None,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {
            ATTR_EFFECT: "Rainbow",
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_INTENSITY: 200,
            ATTR_REVERSE: True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 6
    mock_wled.segment.assert_called_with(
        effect="Rainbow",
        intensity=200,
        reverse=True,
        segment_id=0,
        palette=None,
        speed=None,
    )


async def test_effect_service_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED effect service."""
    mock_wled.segment.side_effect = WLEDError

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_EFFECT: 9},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_ON
    assert "Invalid response from API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        effect=9, segment_id=0, intensity=None, palette=None, reverse=None, speed=None
    )


async def test_preset_service(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the preset service of a WLED light."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESET,
        {
            ATTR_ENTITY_ID: "light.wled_rgb_light",
            ATTR_PRESET: 1,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.preset.call_count == 1
    mock_wled.preset.assert_called_with(preset=1)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESET,
        {
            ATTR_ENTITY_ID: "light.wled_rgb_light_master",
            ATTR_PRESET: 2,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.preset.call_count == 2
    mock_wled.preset.assert_called_with(preset=2)

    assert "The 'wled.preset' service is deprecated" in caplog.text


async def test_preset_service_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED preset service."""
    mock_wled.preset.side_effect = WLEDError

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESET,
        {ATTR_ENTITY_ID: "light.wled_rgb_light", ATTR_PRESET: 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light")
    assert state
    assert state.state == STATE_ON
    assert "Invalid response from API" in caplog.text
    assert mock_wled.preset.call_count == 1
    mock_wled.preset.assert_called_with(preset=1)


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_single_segment_with_keep_master_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the behavior of the integration with a single segment."""
    assert not hass.states.get("light.wled_rgb_light_master")

    hass.config_entries.async_update_entry(
        init_integration, options={CONF_KEEP_MASTER_LIGHT: True}
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_rgb_light_master")
    assert state
    assert state.state == STATE_ON
