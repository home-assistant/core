"""Tests for the Bosch SHC light platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.bosch_shc.const import DOMAIN, OPT_EXCLUDED_DEVICES
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_TOKEN,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import color as color_util

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry


def make_light_switch(
    device_id: str = "light-1",
    name: str = "Test Light",
    binarystate: bool = True,
    status: str = "AVAILABLE",
    # Feature flags
    supports_brightness: bool = False,
    supports_color_hsb: bool = False,
    supports_color_temp: bool = False,
    # Feature values
    brightness: int | None = None,
    rgb: int = 0,
    color: int | None = None,
    min_color_temperature: int | None = None,
    max_color_temperature: int | None = None,
) -> MagicMock:
    """Build a mock device for a LightSwitch entity."""
    device = make_device(device_id=device_id, name=name)
    device.status = status
    device.binarystate = binarystate
    device.supports_brightness = supports_brightness
    device.supports_color_hsb = supports_color_hsb
    device.supports_color_temp = supports_color_temp
    device.brightness = brightness
    device.rgb = rgb
    device.color = color
    device.min_color_temperature = min_color_temperature
    device.max_color_temperature = max_color_temperature
    device.async_set_binarystate = AsyncMock()
    device.async_set_brightness = AsyncMock()
    device.async_set_rgb = AsyncMock()
    device.async_set_color = AsyncMock()
    return device


def make_motion_detector_light(
    device_id: str = "md2-1",
    name: str = "Motion Detector 2",
    binaryswitch: bool = True,
    multi_level_switch: int | None = 80,
    status: str = "AVAILABLE",
) -> MagicMock:
    """Build a mock device for a MotionDetectorLight entity."""
    device = make_device(device_id=device_id, name=name)
    device.status = status
    device.binaryswitch = binaryswitch
    device.multi_level_switch = multi_level_switch
    device.async_set_binaryswitch = AsyncMock()
    device.async_set_multi_level_switch = AsyncMock()
    return device


# ---------------------------------------------------------------------------
# LightSwitch — ONOFF mode (no brightness / color features)
# ---------------------------------------------------------------------------


async def test_ledvance_light_onoff_mode_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with no extra features uses ONOFF color mode and reports on."""
    device = make_light_switch(device_id="led-1", name="Ledvance", binarystate=True)
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.ledvance")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_ledvance_light_onoff_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with no extra features reports off state."""
    device = make_light_switch(device_id="led-2", name="Ledvance Off", binarystate=False)
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.ledvance_off")
    assert state is not None
    assert state.state == STATE_OFF


async def test_ledvance_light_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with non-AVAILABLE status is reported as unavailable."""
    device = make_light_switch(
        device_id="led-3", name="Ledvance Unavail", status="UNAVAILABLE"
    )
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.ledvance_unavail")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_ledvance_light_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with no kwargs calls async_set_binarystate(True) when off."""
    device = make_light_switch(device_id="led-4", name="Ledvance TurnOn", binarystate=False)
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.ledvance_turnon"}, blocking=True
    )

    device.async_set_binarystate.assert_awaited_once_with(True)
    device.async_set_brightness.assert_not_awaited()


async def test_ledvance_light_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_off calls async_set_binarystate(False)."""
    device = make_light_switch(device_id="led-5", name="Ledvance TurnOff", binarystate=True)
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.ledvance_turnoff"}, blocking=True
    )

    device.async_set_binarystate.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# LightSwitch — BRIGHTNESS mode
# ---------------------------------------------------------------------------


async def test_micromodule_dimmer_brightness_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with supports_brightness uses BRIGHTNESS color mode."""
    device = make_light_switch(
        device_id="dim-1",
        name="Dimmer",
        binarystate=True,
        supports_brightness=True,
        brightness=50,
    )
    mock_setup_dependencies.device_helper.micromodule_dimmers = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.dimmer")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    # 50 % → round(50 * 255 / 100) = 128
    assert state.attributes[ATTR_BRIGHTNESS] == 128


async def test_micromodule_dimmer_brightness_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When device.brightness is None the entity brightness attribute is None."""
    device = make_light_switch(
        device_id="dim-2",
        name="Dimmer None",
        binarystate=True,
        supports_brightness=True,
        brightness=None,
    )
    mock_setup_dependencies.device_helper.micromodule_dimmers = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.dimmer_none")
    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


async def test_micromodule_dimmer_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with ATTR_BRIGHTNESS calls async_set_brightness with scaled value."""
    device = make_light_switch(
        device_id="dim-3",
        name="Dimmer Bri",
        binarystate=True,
        supports_brightness=True,
        brightness=100,
    )
    mock_setup_dependencies.device_helper.micromodule_dimmers = [device]

    await setup_integration(hass, mock_config_entry)

    # HA brightness 128 → Bosch 50 %
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.dimmer_bri", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    device.async_set_brightness.assert_awaited_once_with(50)
    # Already on → binarystate setter not called again
    device.async_set_binarystate.assert_not_awaited()


async def test_micromodule_dimmer_turn_on_brightness_zero_clamped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Near-zero HA brightness is clamped to 1 (Bosch API rejects 0)."""
    device = make_light_switch(
        device_id="dim-4",
        name="Dimmer Clamp",
        binarystate=True,
        supports_brightness=True,
        brightness=100,
    )
    mock_setup_dependencies.device_helper.micromodule_dimmers = [device]

    await setup_integration(hass, mock_config_entry)

    # HA brightness=1 → raw 0 % → clamped to 1
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.dimmer_clamp", ATTR_BRIGHTNESS: 1},
        blocking=True,
    )

    device.async_set_brightness.assert_awaited_once_with(1)


# ---------------------------------------------------------------------------
# LightSwitch — COLOR_TEMP mode
# ---------------------------------------------------------------------------


async def test_hue_light_color_temp_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with supports_color_temp uses COLOR_TEMP mode."""
    device = make_light_switch(
        device_id="hue-1",
        name="Hue CT",
        binarystate=True,
        supports_color_temp=True,
        color=200,  # mired → 5000 K
        min_color_temperature=153,
        max_color_temperature=500,
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.hue_ct")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 5000
    # min/max Kelvin derived from mired limits
    assert state.attributes["min_color_temp_kelvin"] == color_util.color_temperature_mired_to_kelvin(153)
    assert state.attributes["max_color_temp_kelvin"] == color_util.color_temperature_mired_to_kelvin(500)


async def test_hue_light_color_temp_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When device.color is falsy, color_temp_kelvin returns None."""
    device = make_light_switch(
        device_id="hue-2",
        name="Hue CT None",
        binarystate=True,
        supports_color_temp=True,
        color=0,  # falsy → None
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.hue_ct_none")
    assert state is not None
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) is None


async def test_hue_light_turn_on_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with ATTR_COLOR_TEMP_KELVIN calls async_set_color with mired value."""
    device = make_light_switch(
        device_id="hue-3",
        name="Hue CT Set",
        binarystate=True,
        supports_color_temp=True,
        color=200,
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    # kelvin 5000 → mired 200
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_ct_set", ATTR_COLOR_TEMP_KELVIN: 5000},
        blocking=True,
    )

    device.async_set_color.assert_awaited_once_with(200)
    device.async_set_binarystate.assert_not_awaited()


# ---------------------------------------------------------------------------
# LightSwitch — HS (full-colour) mode
# ---------------------------------------------------------------------------


async def test_hue_light_hs_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch with supports_color_hsb uses HS color mode."""
    # raw green: rgb(0,255,0) = 0x00FF00 = 65280
    device = make_light_switch(
        device_id="hue-4",
        name="Hue HS",
        binarystate=True,
        supports_color_hsb=True,
        rgb=65280,  # (0, 255, 0) = green
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.hue_hs")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]
    hs = state.attributes[ATTR_HS_COLOR]
    assert hs is not None
    assert round(hs[0]) == 120  # hue 120° = green
    assert round(hs[1]) == 100  # 100 % saturation


async def test_hue_light_turn_on_hs_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with ATTR_HS_COLOR calls async_set_rgb with packed int."""
    device = make_light_switch(
        device_id="hue-5",
        name="Hue HS Set",
        binarystate=True,
        supports_color_hsb=True,
        rgb=0,
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    # hs (120, 100) → rgb (0, 255, 0) → raw 65280
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_hs_set", ATTR_HS_COLOR: (120.0, 100.0)},
        blocking=True,
    )

    device.async_set_rgb.assert_awaited_once_with(65280)
    device.async_set_binarystate.assert_not_awaited()


# ---------------------------------------------------------------------------
# LightSwitch — both HS + COLOR_TEMP supported (HS takes priority)
# ---------------------------------------------------------------------------


async def test_light_both_hs_and_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When both HS and COLOR_TEMP are supported, HS takes priority as color_mode."""
    device = make_light_switch(
        device_id="hue-6",
        name="Hue Full",
        binarystate=True,
        supports_color_hsb=True,
        supports_color_temp=True,
        rgb=65280,
        color=200,
        min_color_temperature=153,
        max_color_temperature=500,
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.hue_full")
    assert state is not None
    # Both modes present, but HS is the initial color_mode
    supported = state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert ColorMode.HS in supported
    assert ColorMode.COLOR_TEMP in supported
    assert state.attributes.get("color_mode") == ColorMode.HS


async def test_light_turn_on_ct_then_hs_when_both_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with COLOR_TEMP then turn_on with HS each call the right setter."""
    device = make_light_switch(
        device_id="hue-7",
        name="Hue Dual",
        binarystate=True,
        supports_color_hsb=True,
        supports_color_temp=True,
        rgb=0,
        color=200,
    )
    mock_setup_dependencies.device_helper.hue_lights = [device]

    await setup_integration(hass, mock_config_entry)

    # First call: set color temperature → kelvin 5000 = mired 200
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_dual", ATTR_COLOR_TEMP_KELVIN: 5000},
        blocking=True,
    )
    device.async_set_color.assert_awaited_once_with(200)
    device.async_set_rgb.assert_not_awaited()

    device.async_set_color.reset_mock()

    # Second call: set HS color → rgb (0, 255, 0) = raw 65280
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_dual", ATTR_HS_COLOR: (120.0, 100.0)},
        blocking=True,
    )
    device.async_set_rgb.assert_awaited_once_with(65280)
    device.async_set_color.assert_not_awaited()


# ---------------------------------------------------------------------------
# LightSwitch — turn_on when already on (binarystate=True)
# ---------------------------------------------------------------------------


async def test_turn_on_when_already_on_skips_binarystate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When the light is already on, async_set_binarystate is not called."""
    device = make_light_switch(
        device_id="led-6",
        name="Already On",
        binarystate=True,
        supports_brightness=True,
        brightness=100,
    )
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.already_on", ATTR_BRIGHTNESS: 200},
        blocking=True,
    )

    device.async_set_brightness.assert_awaited_once()
    device.async_set_binarystate.assert_not_awaited()


async def test_turn_on_when_off_sets_binarystate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When light is off, turn_on sets brightness AND calls binarystate(True)."""
    device = make_light_switch(
        device_id="led-7",
        name="Was Off",
        binarystate=False,
        supports_brightness=True,
        brightness=0,
    )
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.was_off", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    device.async_set_brightness.assert_awaited_once_with(50)
    device.async_set_binarystate.assert_awaited_once_with(True)


# ---------------------------------------------------------------------------
# LightSwitch — multiple collections injected simultaneously
# ---------------------------------------------------------------------------


async def test_multiple_light_collections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Devices from ledvance_lights, micromodule_dimmers and hue_lights are all set up."""
    ledvance = make_light_switch(device_id="led-8", name="Ledvance Multi")
    dimmer = make_light_switch(
        device_id="dim-5", name="Dimmer Multi", supports_brightness=True, brightness=75
    )
    hue = make_light_switch(
        device_id="hue-8", name="Hue Multi", supports_color_hsb=True, rgb=0xFF0000
    )

    mock_setup_dependencies.device_helper.ledvance_lights = [ledvance]
    mock_setup_dependencies.device_helper.micromodule_dimmers = [dimmer]
    mock_setup_dependencies.device_helper.hue_lights = [hue]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.ledvance_multi") is not None
    assert hass.states.get("light.dimmer_multi") is not None
    assert hass.states.get("light.hue_multi") is not None


# ---------------------------------------------------------------------------
# LightSwitch — unique_id
# ---------------------------------------------------------------------------


async def test_light_switch_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch unique_id is <root_device_id>_<device_id>."""
    device = make_light_switch(device_id="led-uid", name="UID Light")
    mock_setup_dependencies.device_helper.ledvance_lights = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("light.uid_light")
    assert entry is not None
    # SHCEntity sets unique_id = f"{root_device_id}_{device_id}"
    assert entry.unique_id == "shc-root_led-uid"


# ---------------------------------------------------------------------------
# MotionDetectorLight
# ---------------------------------------------------------------------------


async def test_motion_detector_light_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetectorLight entity is created from motion_detectors2 collection."""
    device = make_motion_detector_light(
        device_id="md2-1", name="Corridor", binaryswitch=True, multi_level_switch=80
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    # entity name = device name + " Motion Light" (has_entity_name + _attr_name)
    state = hass.states.get("light.corridor_motion_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    # 80 % → round(80 * 255 / 100) = 204
    assert state.attributes[ATTR_BRIGHTNESS] == 204


async def test_motion_detector_light_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetectorLight reports off when binaryswitch is False."""
    device = make_motion_detector_light(
        device_id="md2-2", name="Hallway", binaryswitch=False, multi_level_switch=50
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.hallway_motion_light")
    assert state is not None
    assert state.state == STATE_OFF


async def test_motion_detector_light_multi_level_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetectorLight brightness is 0 when multi_level_switch is None."""
    device = make_motion_detector_light(
        device_id="md2-3", name="Garage", binaryswitch=True, multi_level_switch=None
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.garage_motion_light")
    assert state is not None
    # brightness property returns 0 when multi_level_switch is None
    assert state.attributes[ATTR_BRIGHTNESS] == 0


async def test_motion_detector_light_turn_on_no_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on without brightness only calls binaryswitch when light is off."""
    device = make_motion_detector_light(
        device_id="md2-4", name="Porch", binaryswitch=False, multi_level_switch=50
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.porch_motion_light"}, blocking=True
    )

    device.async_set_binaryswitch.assert_awaited_once_with(True)
    device.async_set_multi_level_switch.assert_not_awaited()


async def test_motion_detector_light_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_on with brightness sets level and switches on when off."""
    device = make_motion_detector_light(
        device_id="md2-5", name="Entry", binaryswitch=False, multi_level_switch=0
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    # HA brightness 204 → level round(204*100/255) = 80
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.entry_motion_light", ATTR_BRIGHTNESS: 204},
        blocking=True,
    )

    device.async_set_multi_level_switch.assert_awaited_once_with(80)
    device.async_set_binaryswitch.assert_awaited_once_with(True)


async def test_motion_detector_light_turn_on_brightness_clamped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Near-zero HA brightness is clamped to level 1."""
    device = make_motion_detector_light(
        device_id="md2-6", name="Stair", binaryswitch=True, multi_level_switch=50
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.stair_motion_light", ATTR_BRIGHTNESS: 1},
        blocking=True,
    )

    device.async_set_multi_level_switch.assert_awaited_once_with(1)


async def test_motion_detector_light_turn_on_already_on_skips_binaryswitch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When motion light is already on, async_set_binaryswitch is not called."""
    device = make_motion_detector_light(
        device_id="md2-7", name="Lounge", binaryswitch=True, multi_level_switch=80
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.lounge_motion_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    device.async_set_multi_level_switch.assert_awaited_once()
    device.async_set_binaryswitch.assert_not_awaited()


async def test_motion_detector_light_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """turn_off calls async_set_binaryswitch(False)."""
    device = make_motion_detector_light(
        device_id="md2-8", name="Study", binaryswitch=True, multi_level_switch=80
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.study_motion_light"}, blocking=True
    )

    device.async_set_binaryswitch.assert_awaited_once_with(False)


async def test_motion_detector_light_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetectorLight unique_id follows the <root>_<id>_motionlight pattern."""
    device = make_motion_detector_light(device_id="md2-uid", name="UID Detector")
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("light.uid_detector_motion_light")
    assert entry is not None
    assert entry.unique_id == "shc-root_md2-uid_motionlight"


async def test_motion_detector_light_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetectorLight is unavailable when device status is not AVAILABLE."""
    device = make_motion_detector_light(
        device_id="md2-9", name="Gone", status="UNAVAILABLE"
    )
    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.gone_motion_light")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# device_excluded path — covers the `continue` branches in async_setup_entry
# ---------------------------------------------------------------------------


async def test_excluded_light_switch_not_added(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A LightSwitch device listed in excluded_devices is not added as entity."""
    excluded = make_light_switch(device_id="excl-1", name="Excluded Ledvance")
    mock_setup_dependencies.device_helper.ledvance_lights = [excluded]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac-excl",
        entry_id="EXCL0000000000000000000001",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["excl-1"]},
    )
    await setup_integration(hass, entry)

    assert hass.states.get("light.excluded_ledvance") is None


async def test_excluded_motion_detector_light_not_added(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A MotionDetectorLight device listed in excluded_devices is not added as entity."""
    excluded = make_motion_detector_light(device_id="excl-md2", name="Excluded MD2")
    mock_setup_dependencies.device_helper.motion_detectors2 = [excluded]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac-excl2",
        entry_id="EXCL0000000000000000000002",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["excl-md2"]},
    )
    await setup_integration(hass, entry)

    assert hass.states.get("light.excluded_md2_motion_light") is None
