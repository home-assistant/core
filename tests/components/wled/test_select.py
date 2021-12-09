"""Tests for the WLED select platform."""
import json
from unittest.mock import MagicMock

import pytest
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.select.const import ATTR_OPTION, ATTR_OPTIONS
from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ENTITY_CATEGORY_CONFIG,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_color_palette_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the creation and values of the WLED selects."""
    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:palette-outline"
    assert state.attributes.get(ATTR_OPTIONS) == [
        "Analogous",
        "April Night",
        "Autumn",
        "Based on Primary",
        "Based on Set",
        "Beach",
        "Beech",
        "Breeze",
        "C9",
        "Cloud",
        "Cyane",
        "Default",
        "Departure",
        "Drywet",
        "Fire",
        "Forest",
        "Grintage",
        "Hult",
        "Hult 64",
        "Icefire",
        "Jul",
        "Landscape",
        "Lava",
        "Light Pink",
        "Magenta",
        "Magred",
        "Ocean",
        "Orange & Teal",
        "Orangery",
        "Party",
        "Pastel",
        "Primary Color",
        "Rainbow",
        "Rainbow Bands",
        "Random Cycle",
        "Red & Blue",
        "Rewhi",
        "Rivendell",
        "Sakura",
        "Set Colors",
        "Sherbet",
        "Splash",
        "Sunset",
        "Sunset 2",
        "Tertiary",
        "Tiamat",
        "Vintage",
        "Yelblu",
        "Yellowout",
        "Yelmag",
    ]
    assert state.state == "Random Cycle"

    entry = entity_registry.async_get("select.wled_rgb_light_segment_1_color_palette")
    assert entry
    assert entry.unique_id == "aabbccddeeff_palette_1"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG


async def test_color_palette_segment_change_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the option change of state of the WLED segments."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Icefire",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        segment_id=1,
        palette="Icefire",
    )


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_color_palette_dynamically_handle_segments(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert not segment1

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert segment1
    assert segment1.state == "Random Cycle"

    # Test adding if segment shows up again, including the master entity
    mock_wled.update.return_value = return_value
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("select.wled_rgb_light_color_palette")
    segment1 = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert segment0
    assert segment0.state == "Default"
    assert segment1
    assert segment1.state == STATE_UNAVAILABLE


async def test_color_palette_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.segment.side_effect = WLEDError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Icefire",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.state == "Random Cycle"
    assert "Invalid response from API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=1, palette="Icefire")


async def test_color_palette_select_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.segment.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_segment_1_color_palette",
            ATTR_OPTION: "Icefire",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=1, palette="Icefire")


async def test_preset_unavailable_without_presets(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WLED preset entity is unavailable when presets are not available."""
    state = hass.states.get("select.wled_rgb_light_preset")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_preset_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the creation and values of the WLED selects."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("select.wled_rgbw_light_preset")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:playlist-play"
    assert state.attributes.get(ATTR_OPTIONS) == ["Preset 1", "Preset 2"]
    assert state.state == "Preset 1"

    entry = entity_registry.async_get("select.wled_rgbw_light_preset")
    assert entry
    assert entry.unique_id == "aabbccddee11_preset"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_preset",
            ATTR_OPTION: "Preset 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.preset.call_count == 1
    mock_wled.preset.assert_called_with(preset="Preset 2")


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_old_style_preset_active(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unknown preset returned (when old style/unknown) preset is active."""
    # Set device preset state to a random number
    mock_wled.update.return_value.state.preset = 99

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_preset")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_preset_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.preset.side_effect = WLEDError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_preset",
            ATTR_OPTION: "Preset 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_preset")
    assert state
    assert state.state == "Preset 1"
    assert "Invalid response from API" in caplog.text
    assert mock_wled.preset.call_count == 1
    mock_wled.preset.assert_called_with(preset="Preset 2")


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_preset_select_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.preset.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_preset",
            ATTR_OPTION: "Preset 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_preset")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.preset.call_count == 1
    mock_wled.preset.assert_called_with(preset="Preset 2")


async def test_playlist_unavailable_without_playlists(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WLED playlist entity is unavailable when playlists are not available."""
    state = hass.states.get("select.wled_rgb_light_playlist")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_playlist_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the creation and values of the WLED selects."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("select.wled_rgbw_light_playlist")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:play-speed"
    assert state.attributes.get(ATTR_OPTIONS) == ["Playlist 1", "Playlist 2"]
    assert state.state == "Playlist 1"

    entry = entity_registry.async_get("select.wled_rgbw_light_playlist")
    assert entry
    assert entry.unique_id == "aabbccddee11_playlist"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_playlist",
            ATTR_OPTION: "Playlist 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.playlist.call_count == 1
    mock_wled.playlist.assert_called_with(playlist="Playlist 2")


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_old_style_playlist_active(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when old style playlist cycle is active."""
    # Set device playlist to 0, which meant "cycle" previously.
    mock_wled.update.return_value.state.playlist = 0

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_playlist")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_playlist_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.playlist.side_effect = WLEDError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_playlist",
            ATTR_OPTION: "Playlist 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_playlist")
    assert state
    assert state.state == "Playlist 1"
    assert "Invalid response from API" in caplog.text
    assert mock_wled.playlist.call_count == 1
    mock_wled.playlist.assert_called_with(playlist="Playlist 2")


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_playlist_select_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.playlist.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgbw_light_playlist",
            ATTR_OPTION: "Playlist 2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgbw_light_playlist")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.playlist.call_count == 1
    mock_wled.playlist.assert_called_with(playlist="Playlist 2")


async def test_live_override(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the creation and values of the WLED selects."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("select.wled_rgb_light_live_override")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:theater"
    assert state.attributes.get(ATTR_OPTIONS) == ["0", "1", "2"]
    assert state.state == "0"

    entry = entity_registry.async_get("select.wled_rgb_light_live_override")
    assert entry
    assert entry.unique_id == "aabbccddeeff_live_override"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_live_override",
            ATTR_OPTION: "2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.live.call_count == 1
    mock_wled.live.assert_called_with(live=2)


async def test_live_select_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.live.side_effect = WLEDError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_live_override",
            ATTR_OPTION: "1",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_live_override")
    assert state
    assert state.state == "0"
    assert "Invalid response from API" in caplog.text
    assert mock_wled.live.call_count == 1
    mock_wled.live.assert_called_with(live=1)


async def test_live_select_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED selects."""
    mock_wled.live.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.wled_rgb_light_live_override",
            ATTR_OPTION: "2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.wled_rgb_light_live_override")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text
    assert mock_wled.live.call_count == 1
    mock_wled.live.assert_called_with(live=2)
