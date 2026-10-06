"""Tests for the WLED light platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.components.wled.const import (
    CONF_KEEP_MAIN_LIGHT,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_GROUP_ENTITIES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.wled.PLATFORMS", [Platform.LIGHT]):
        yield


@pytest.mark.parametrize(
    "device_fixture", ["cct", "rgb_single_segment", "rgb", "rgb_websocket", "rgbw"]
)
async def test_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshots of the platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_segment_with_sparse_ids(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test segment lights still set up after a segment in the middle is deleted."""
    data = await async_load_json_object_fixture(hass, "rgb.json", DOMAIN)
    data["state"]["seg"][1]["id"] = 2
    mock_wled.update.return_value = WLEDDevice.from_dict(data)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_rgb_light_segment_2"))
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]


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
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    assert (segment0 := hass.states.get("light.wled_rgb_light"))
    assert segment0.state == STATE_ON
    assert not hass.states.get("light.wled_rgb_light_main")
    assert not hass.states.get("light.wled_rgb_light_segment_1")

    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice.from_dict(
        await async_load_json_object_fixture(hass, "rgb.json", DOMAIN)
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (main := hass.states.get("light.wled_rgb_light_main"))
    assert main.state == STATE_ON
    assert (segment0 := hass.states.get("light.wled_rgb_light"))
    assert segment0.state == STATE_ON
    assert (segment1 := hass.states.get("light.wled_rgb_light_segment_1"))
    assert segment1.state == STATE_ON

    # Test adding if segment shows up again, including the main entity
    mock_wled.update.return_value = return_value
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
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
    freezer: FrozenDateTimeFactory,
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
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.attributes.get(ATTR_BRIGHTNESS) == 100

    # Test segment is off when main is off
    device.state.on = False
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
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
    mock_wled.segment.assert_called_with(
        on=True, segment_id=0, brightness=255, transition=50
    )
    mock_wled.master.assert_called_with(on=True, transition=50, brightness=42)


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_translation_key"),
    [
        (WLEDError, STATE_ON, "invalid_response_wled_error"),
        (WLEDConnectionError, STATE_UNAVAILABLE, "connection_error"),
    ],
)
async def test_light_errors(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    side_effect: Exception,
    expected_state: str,
    expected_translation_key: str,
) -> None:
    """Test error handling of the WLED lights."""
    mock_wled.segment.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as ex:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.wled_rgb_light"},
            blocking=True,
        )

    assert ex.value.translation_domain == DOMAIN
    assert ex.value.translation_key == expected_translation_key

    assert (state := hass.states.get("light.wled_rgb_light"))
    assert state.state == expected_state
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(on=False, segment_id=0, transition=None)


@pytest.mark.parametrize("device_fixture", ["rgbw"])
async def test_rgbw_light(hass: HomeAssistant, mock_wled: MagicMock) -> None:
    """Test RGBW support for WLED."""
    assert (state := hass.states.get("light.wled_rgbw_light"))
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.RGBW]
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.RGBW
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
        init_integration, options={CONF_KEEP_MAIN_LIGHT: True}
    )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["cct"])
async def test_cct_light(hass: HomeAssistant, mock_wled: MagicMock) -> None:
    """Test CCT support for WLED."""
    assert (state := hass.states.get("light.wled_cct_light"))
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGBW,
    ]
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.COLOR_TEMP
    assert state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN) == 2000
    assert state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN) == 6535
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) == 2942

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.wled_cct_light",
            ATTR_COLOR_TEMP_KELVIN: 4321,
        },
        blocking=True,
    )
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(
        cct=130,
        color_primary=(0, 0, 0, 255),
        on=True,
        segment_id=0,
    )


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_main_light_group_updates_when_segments_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that the main light group field updates when segments are dynamically added or removed."""
    single_segment_data = mock_wled.update.return_value
    two_segment_data = WLEDDevice.from_dict(
        await async_load_json_object_fixture(hass, "rgb.json", DOMAIN)
    )

    # Enable keep_main_light so the main light persists even with a single segment
    hass.config_entries.async_update_entry(
        init_integration, options={CONF_KEEP_MAIN_LIGHT: True}
    )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    # 1 segment: group should contain only segment 0
    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_GROUP_ENTITIES] == ["light.wled_rgb_light"]

    # Add a second segment
    mock_wled.update.return_value = two_segment_data
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # 2 segments: group should contain both
    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.attributes[ATTR_GROUP_ENTITIES] == [
        "light.wled_rgb_light",
        "light.wled_rgb_light_segment_1",
    ]

    # Remove the second segment
    mock_wled.update.return_value = single_segment_data
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Back to 1 segment: group should contain only segment 0 again
    assert (state := hass.states.get("light.wled_rgb_light_main"))
    assert state.attributes[ATTR_GROUP_ENTITIES] == ["light.wled_rgb_light"]


async def _async_load_segment(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
    light_capabilities: int,
    color: list[int],
) -> None:
    """Load the CCT device with one segment of the given capabilities and color."""
    data = await async_load_json_object_fixture(hass, "cct.json", DOMAIN)
    data["info"]["leds"]["seglc"] = [light_capabilities]
    data["state"]["seg"][0]["col"] = [color, [0, 0, 0, 0], [0, 0, 0, 0]]
    mock_wled.update.return_value = WLEDDevice.from_dict(data)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize("device_fixture", ["cct"])
@pytest.mark.parametrize(
    ("light_capabilities", "color", "supported_color_modes", "color_mode"),
    [
        # RGB + white channel + color temperature
        (
            7,
            [0, 0, 0, 255],
            [ColorMode.COLOR_TEMP, ColorMode.RGBW],
            ColorMode.COLOR_TEMP,
        ),
        (7, [255, 0, 0, 0], [ColorMode.COLOR_TEMP, ColorMode.RGBW], ColorMode.RGBW),
        (7, [255, 0, 0, 128], [ColorMode.COLOR_TEMP, ColorMode.RGBW], ColorMode.RGBW),
        # A dimmed white channel is an RGBW color, not a color temperature.
        (7, [0, 0, 0, 64], [ColorMode.COLOR_TEMP, ColorMode.RGBW], ColorMode.RGBW),
        (7, [0, 0, 0, 0], [ColorMode.COLOR_TEMP, ColorMode.RGBW], ColorMode.RGBW),
        # RGB + color temperature
        (
            5,
            [255, 255, 255],
            [ColorMode.COLOR_TEMP, ColorMode.RGB],
            ColorMode.COLOR_TEMP,
        ),
        (5, [255, 0, 0], [ColorMode.COLOR_TEMP, ColorMode.RGB], ColorMode.RGB),
        (5, [128, 128, 128], [ColorMode.COLOR_TEMP, ColorMode.RGB], ColorMode.RGB),
        # Single color modes
        (1, [255, 0, 0], [ColorMode.RGB], ColorMode.RGB),
        (3, [255, 0, 0, 128], [ColorMode.RGBW], ColorMode.RGBW),
        (6, [0, 0, 0, 255], [ColorMode.COLOR_TEMP], ColorMode.COLOR_TEMP),
        # Manual white (bit 8, not set by current firmware) never gives an
        # unsupported color mode, and recognizes the white it sends.
        (11, [0, 0, 0, 255], [ColorMode.RGBW, ColorMode.WHITE], ColorMode.RGBW),
        (
            13,
            [255, 255, 255],
            [ColorMode.COLOR_TEMP, ColorMode.RGBW],
            ColorMode.COLOR_TEMP,
        ),
    ],
)
async def test_color_mode_follows_color(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
    light_capabilities: int,
    color: list[int],
    supported_color_modes: list[ColorMode],
    color_mode: ColorMode,
) -> None:
    """Test the color mode follows the segment's capabilities and color."""
    await _async_load_segment(
        hass, mock_wled, mock_config_entry, light_capabilities, color
    )

    assert (state := hass.states.get("light.wled_cct_light"))
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == supported_color_modes
    assert state.attributes[ATTR_COLOR_MODE] == color_mode


@pytest.mark.parametrize("device_fixture", ["cct"])
async def test_color_mode_changes_with_the_device(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the color mode follows a color change on the device."""
    await _async_load_segment(hass, mock_wled, mock_config_entry, 7, [0, 0, 0, 255])
    assert (state := hass.states.get("light.wled_cct_light"))
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    data = await async_load_json_object_fixture(hass, "cct.json", DOMAIN)
    data["state"]["seg"][0]["col"] = [[255, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    mock_wled.update.return_value = WLEDDevice.from_dict(data)
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("light.wled_cct_light"))
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBW
    assert state.attributes[ATTR_RGBW_COLOR] == (255, 0, 0, 0)


@pytest.mark.parametrize("device_fixture", ["cct"])
@pytest.mark.parametrize(
    ("light_capabilities", "color", "color_primary"),
    [
        (7, [255, 0, 0, 0], (0, 0, 0, 255)),
        (6, [0, 0, 0, 255], (0, 0, 0, 255)),
        (5, [255, 0, 0], (255, 255, 255)),
    ],
)
async def test_color_temp_sets_white(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
    light_capabilities: int,
    color: list[int],
    color_primary: tuple[int, ...],
) -> None:
    """Test a color temperature turns on the white it shows on."""
    await _async_load_segment(
        hass, mock_wled, mock_config_entry, light_capabilities, color
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.wled_cct_light", ATTR_COLOR_TEMP_KELVIN: 4321},
        blocking=True,
    )

    mock_wled.segment.assert_called_with(
        cct=130, color_primary=color_primary, on=True, segment_id=0
    )


@pytest.mark.parametrize("device_fixture", ["cct"])
@pytest.mark.parametrize(
    ("light_capabilities", "color", "service_data", "color_primary"),
    [
        (7, [0, 0, 0, 255], {ATTR_RGBW_COLOR: (255, 0, 0, 0)}, (255, 0, 0, 0)),
        (5, [255, 255, 255], {ATTR_RGB_COLOR: (255, 0, 0)}, (255, 0, 0)),
    ],
)
async def test_color_leaves_color_temp_alone(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    mock_config_entry: MockConfigEntry,
    light_capabilities: int,
    color: list[int],
    service_data: dict[str, Any],
    color_primary: tuple[int, ...],
) -> None:
    """Test setting a color doesn't change the color temperature."""
    await _async_load_segment(
        hass, mock_wled, mock_config_entry, light_capabilities, color
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.wled_cct_light", **service_data},
        blocking=True,
    )

    mock_wled.segment.assert_called_with(
        color_primary=color_primary, on=True, segment_id=0
    )
