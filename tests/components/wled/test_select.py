"""Tests for the WLED select platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.components.wled.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_time_changed, load_json_object_fixture

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "option", "method", "called_with"),
    [
        (
            "rgb",
            "select.wled_rgb_light_segment_1_color_palette",
            "Icefire",
            "segment",
            {"segment_id": 1, "palette": "Icefire"},
        ),
        (
            "rgb",
            "select.wled_rgb_light_live_override",
            "2",
            "live",
            {"live": 2},
        ),
        (
            "rgbw",
            "select.wled_rgbw_light_playlist",
            "Playlist 2",
            "playlist",
            {"playlist": "Playlist 2"},
        ),
        (
            "rgbw",
            "select.wled_rgbw_light_preset",
            "Preset 2",
            "preset",
            {"preset": "Preset 2"},
        ),
    ],
)
async def test_color_palette_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_wled: MagicMock,
    entity_id: str,
    option: str,
    method: str,
    called_with: dict[str, int | str],
) -> None:
    """Test the creation and values of the WLED selects."""
    # First segment of the strip
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot

    method_mock = getattr(mock_wled, method)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    assert method_mock.call_count == 1
    method_mock.assert_called_with(**called_with)

    # Test invalid response, not becoming unavailable
    method_mock.side_effect = WLEDError
    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: option},
            blocking=True,
        )

    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE
    assert method_mock.call_count == 2
    method_mock.assert_called_with(**called_with)

    # Test connection error, leading to becoming unavailable
    method_mock.side_effect = WLEDConnectionError
    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: option},
            blocking=True,
        )

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE
    assert method_mock.call_count == 3
    method_mock.assert_called_with(**called_with)


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_color_palette_dynamically_handle_segments(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    assert (segment0 := hass.states.get("select.wled_rgb_light_color_palette"))
    assert segment0.state == "Default"
    assert not hass.states.get("select.wled_rgb_light_segment_1_color_palette")

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice.from_dict(
        load_json_object_fixture("rgb.json", DOMAIN)
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get("select.wled_rgb_light_color_palette"))
    assert segment0.state == "Default"
    assert (
        segment1 := hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    )
    assert segment1.state == "* Random Cycle"

    # Test adding if segment shows up again, including the master entity
    mock_wled.update.return_value = return_value
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get("select.wled_rgb_light_color_palette"))
    assert segment0.state == "Default"
    assert (
        segment1 := hass.states.get("select.wled_rgb_light_segment_1_color_palette")
    )
    assert segment1.state == STATE_UNAVAILABLE


async def test_preset_unavailable_without_presets(hass: HomeAssistant) -> None:
    """Test WLED preset entity is unavailable when presets are not available."""
    assert (state := hass.states.get("select.wled_rgb_light_preset"))
    assert state.state == STATE_UNAVAILABLE


async def test_playlist_unavailable_without_playlists(hass: HomeAssistant) -> None:
    """Test WLED playlist entity is unavailable when playlists are not available."""
    assert (state := hass.states.get("select.wled_rgb_light_playlist"))
    assert state.state == STATE_UNAVAILABLE
