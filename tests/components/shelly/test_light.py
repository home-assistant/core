"""Tests for Shelly light platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, Mock

from aioshelly.const import (
    MODEL_BULB,
    MODEL_BULB_RGBW,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_DUO,
    MODEL_MULTICOLOR_BULB_G3,
    MODEL_RGBW2,
    MODEL_VINTAGE_V2,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityFeature,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    get_entity,
    init_integration,
    mutate_rpc_device_status,
    patch_platforms,
    register_device,
    register_entity,
)
from .conftest import (
    MOCK_LEDSTRIP_EFFECTS,
    MOCK_LEDSTRIP_STATUS_AURORA,
    MOCK_LEDSTRIP_STATUS_BLINK,
    MOCK_LEDSTRIP_STATUS_RAINBOW,
    MOCK_LEDSTRIP_STATUS_SOLID,
    mock_white_light_set_state,
)

RELAY_BLOCK_ID = 0
LIGHT_BLOCK_ID = 2
SHELLY_PLUS_RGBW_CHANNELS = 4
LEDSTRIP_ENTITY_ID = f"{LIGHT_DOMAIN}.test_name"
LEDSTRIP_BACKGROUND_ENTITY_ID = f"{LIGHT_DOMAIN}.test_name_effect_background"


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.LIGHT]):
        yield


async def test_block_device_rgbw_bulb(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device RGBW bulb."""
    monkeypatch.setitem(mock_block_device.shelly, "num_outputs", 1)
    entity_id = "light.test_name"
    await init_integration(hass, 1, model=MODEL_BULB)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGBW_COLOR] == (45, 55, 65, 70)
    assert state.attributes[ATTR_BRIGHTNESS] == 48
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGBW,
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.EFFECT
    assert len(state.attributes[ATTR_EFFECT_LIST]) == 7
    assert state.attributes[ATTR_EFFECT] == "Off"

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on, RGBW = [70, 80, 90, 20], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: entity_id,
            LightServiceArgument.RGBW_COLOR: [70, 80, 90, 30],
            LightServiceArgument.BRIGHTNESS: 33,
            LightServiceArgument.EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, white=30, effect=3
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBW
    assert state.attributes[ATTR_RGBW_COLOR] == (70, 80, 90, 30)
    assert state.attributes[ATTR_BRIGHTNESS] == 33
    assert state.attributes[ATTR_EFFECT] == "Flash"

    # Turn on, COLOR_TEMP_KELVIN = 3500
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3500

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-light_0"


async def test_block_device_rgb_bulb(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device RGB bulb."""
    monkeypatch.setitem(mock_block_device.shelly, "num_outputs", 1)
    entity_id = "light.test_name"
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode")
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID], "description", "light_1"
    )
    await init_integration(hass, 1, model=MODEL_BULB_RGBW)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (45, 55, 65)
    assert state.attributes[ATTR_BRIGHTNESS] == 48
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    ]
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
    )
    assert len(state.attributes[ATTR_EFFECT_LIST]) == 4
    assert state.attributes[ATTR_EFFECT] == "Off"

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on, RGB = [70, 80, 90], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: entity_id,
            LightServiceArgument.RGB_COLOR: [70, 80, 90],
            LightServiceArgument.BRIGHTNESS: 33,
            LightServiceArgument.EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, effect=3
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_RGB_COLOR] == (70, 80, 90)
    assert state.attributes[ATTR_BRIGHTNESS] == 33
    assert state.attributes[ATTR_EFFECT] == "Flash"

    # Turn on, COLOR_TEMP_KELVIN = 3500
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3500

    # Turn on with unsupported effect
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.EFFECT: "Breath"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", mode="color"
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Off"
    assert "Effect 'Breath' not supported" in caplog.text

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-light_1"


async def test_block_device_white_bulb(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device white bulb."""
    monkeypatch.setitem(mock_block_device.shelly, "num_outputs", 1)
    entity_id = "light.test_name"
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "red")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "green")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "blue")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "colorTemp")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "effect")
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID], "description", "light_1"
    )
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID],
        "set_state",
        AsyncMock(side_effect=mock_white_light_set_state),
    )
    await init_integration(hass, 1, model=MODEL_VINTAGE_V2)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on, brightness = 33
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS: 33},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 33

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-light_1"


@pytest.mark.parametrize(
    "model",
    [
        MODEL_DUO,
        MODEL_BULB_RGBW,
        MODEL_DIMMER,
        MODEL_DIMMER_2,
        MODEL_RGBW2,
        MODEL_VINTAGE_V2,
    ],
)
async def test_block_device_support_transition(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    model: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device supports transition."""
    # num_outputs is 2, device name and channel name is used
    entity_id = "light.test_name_channel_1"
    monkeypatch.setitem(
        mock_block_device.settings, "fw", "20220809-122808/v1.12-g99f7e0b"
    )
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID], "description", "light_1"
    )
    await init_integration(hass, 1, model=model)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & LightEntityFeature.TRANSITION

    # Turn on, TRANSITION = 4
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.TRANSITION: 4},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", transition=4000
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Turn off, TRANSITION = 6, limit to 5000ms
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.TRANSITION: 6},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off", transition=5000
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-light_1"


async def test_block_device_relay_app_type_light(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device relay in app type set to light mode."""
    entity_id = "light.test_name_channel_1"
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "red")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "green")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "blue")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "mode")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "gain")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "brightness")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "effect")
    monkeypatch.delattr(mock_block_device.blocks[RELAY_BLOCK_ID], "colorTemp")
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    monkeypatch.setattr(
        mock_block_device.blocks[RELAY_BLOCK_ID], "description", "relay_1"
    )
    await init_integration(hass, 1)

    assert hass.states.get("switch.test_name_channel_1") is None

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Turn off
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="on"
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-relay_1"


async def test_block_device_no_light_blocks(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device without light blocks."""
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)

    assert hass.states.get("light.test_name_channel_1") is None


async def test_rpc_device_switch_type_lights_mode(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device with switch in consumption type lights mode."""
    entity_id = "light.test_name_test_switch_0"
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    await init_integration(hass, 2)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.switch_set.assert_called_once_with(0, True)
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    mock_rpc_device.switch_set.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "switch:0", "output", False)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.switch_set.assert_called_once_with(0, False)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-switch:0"


async def test_rpc_light(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC light."""
    entity_id = f"{LIGHT_DOMAIN}.test_name_test_light_0"
    monkeypatch.delitem(mock_rpc_device.status, "switch:0")
    await init_integration(hass, 2)

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.light_set.assert_called_once_with(0, {"on": True})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 135

    # Turn off
    mock_rpc_device.light_set.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", False)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.mock_update()
    mock_rpc_device.light_set.assert_called_once_with(0, {"on": False})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on, brightness = 33
    mock_rpc_device.light_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS: 33},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", True)
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "brightness", 13)
    mock_rpc_device.mock_update()

    mock_rpc_device.light_set.assert_called_once_with(0, {"on": True, "brightness": 13})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 33

    # Turn on, transition = 10.1
    mock_rpc_device.light_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.TRANSITION: 10.1},
        blocking=True,
    )

    mock_rpc_device.mock_update()

    mock_rpc_device.light_set.assert_called_once_with(
        0, {"on": True, "transition_duration": 10.1}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Turn off, transition = 0.4, should be limited to 0.5
    mock_rpc_device.light_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.TRANSITION: 0.4},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", False)
    mock_rpc_device.mock_update()

    mock_rpc_device.light_set.assert_called_once_with(
        0, {"on": False, "transition_duration": 0.5}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-light:0"


async def test_rpc_device_rgb_profile(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device in RGB profile."""
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        monkeypatch.delitem(mock_rpc_device.status, f"light:{i}")
    monkeypatch.delitem(mock_rpc_device.status, "rgbw:0")
    entity_id = "light.test_name_test_rgb_0"
    await init_integration(hass, 2)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (45, 55, 65)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    # Turn on, RGB = [70, 80, 90]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.RGB_COLOR: [70, 80, 90]},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgb:0", "rgb", [70, 80, 90])
    mock_rpc_device.mock_update()

    mock_rpc_device.rgb_set.assert_called_once_with(
        0, {"on": True, "rgb": [70, 80, 90]}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_RGB_COLOR] == (70, 80, 90)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-rgb:0"


async def test_rpc_device_rgbw_profile(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device in RGBW profile."""
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        monkeypatch.delitem(mock_rpc_device.status, f"light:{i}")
    monkeypatch.delitem(mock_rpc_device.status, "rgb:0")
    entity_id = "light.test_name_test_rgbw_0"
    await init_integration(hass, 2)

    # Test initial
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGBW_COLOR] == (21, 22, 23, 120)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBW]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    # Turn on, RGBW = [72, 82, 92, 128]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: entity_id,
            LightServiceArgument.RGBW_COLOR: [72, 82, 92, 128],
        },
        blocking=True,
    )

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "rgbw:0", "rgb", [72, 82, 92]
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgbw:0", "white", 128)
    mock_rpc_device.mock_update()

    mock_rpc_device.rgbw_set.assert_called_once_with(
        0, {"on": True, "rgb": [72, 82, 92], "white": 128}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBW
    assert state.attributes[ATTR_RGBW_COLOR] == (72, 82, 92, 128)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-rgbw:0"


async def test_rpc_rgbw_device_light_mode_remove_others(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Shelly RPC RGBW device in light mode removes RGB/RGBW entities."""
    monkeypatch.delitem(mock_rpc_device.status, "rgb:0")
    monkeypatch.delitem(mock_rpc_device.status, "rgbw:0")

    # register rgb and rgbw lights
    config_entry = await init_integration(hass, 2, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    register_entity(
        hass,
        LIGHT_DOMAIN,
        "test_rgb_0",
        "rgb:0",
        config_entry,
        device_id=device_entry.id,
    )
    register_entity(
        hass,
        LIGHT_DOMAIN,
        "test_rgbw_0",
        "rgbw:0",
        config_entry,
        device_id=device_entry.id,
    )

    # verify RGB & RGBW entities created
    assert get_entity(hass, LIGHT_DOMAIN, "rgb:0") is not None
    assert get_entity(hass, LIGHT_DOMAIN, "rgbw:0") is not None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # verify we have 4 lights
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        entity_id = f"light.test_name_test_light_{i}"

        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_ON

        assert (entry := entity_registry.async_get(entity_id))
        assert entry.unique_id == f"123456789ABC-light:{i}"

    # verify RGB & RGBW entities removed
    assert get_entity(hass, LIGHT_DOMAIN, "rgb:0") is None
    assert get_entity(hass, LIGHT_DOMAIN, "rgbw:0") is None


@pytest.mark.parametrize(
    ("active_mode", "removed_mode"),
    [
        ("rgb", "rgbw"),
        ("rgbw", "rgb"),
    ],
)
async def test_rpc_rgbw_device_rgb_w_modes_remove_others(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    active_mode: str,
    removed_mode: str,
) -> None:
    """Test Shelly RPC RGBW device in RGB/W modes other lights."""
    removed_key = f"{removed_mode}:0"
    config_entry = await init_integration(hass, 2, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)

    # register lights
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        monkeypatch.delitem(mock_rpc_device.status, f"light:{i}")
        entity_id = f"light.test_name_test_light_{i}"
        register_entity(
            hass,
            LIGHT_DOMAIN,
            entity_id,
            f"light:{i}",
            config_entry,
            device_id=device_entry.id,
        )
    monkeypatch.delitem(mock_rpc_device.status, f"{removed_mode}:0")
    register_entity(
        hass,
        LIGHT_DOMAIN,
        f"test_{removed_key}",
        removed_key,
        config_entry,
        device_id=device_entry.id,
    )

    # verify lights entities created
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        assert get_entity(hass, LIGHT_DOMAIN, f"light:{i}") is not None
    assert get_entity(hass, LIGHT_DOMAIN, removed_key) is not None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # verify we have RGB/w light
    entity_id = f"light.test_name_test_{active_mode}_0"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == f"123456789ABC-{active_mode}:0"

    # verify light & RGB/W entities removed
    for i in range(SHELLY_PLUS_RGBW_CHANNELS):
        assert get_entity(hass, LIGHT_DOMAIN, f"light:{i}") is None
    assert get_entity(hass, LIGHT_DOMAIN, removed_key) is None


async def test_rpc_cct_light(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC CCT light."""
    entity_id = f"{LIGHT_DOMAIN}.test_name_cct_light_0"

    config = deepcopy(mock_rpc_device.config)
    config["cct:0"] = {"id": 0, "name": None, "ct_range": [3333, 5555]}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["cct:0"] = {"id": 0, "output": False, "brightness": 77, "ct": 3666}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-cct:0"

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.cct_set.assert_called_once_with(0, {"on": False})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on
    mock_rpc_device.cct_set.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cct:0", "output", True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.mock_update()
    mock_rpc_device.cct_set.assert_called_once_with(0, {"on": True})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_BRIGHTNESS] == 196  # 77% of 255
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3666
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 3333
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 5555

    # Turn on, brightness = 88
    mock_rpc_device.cct_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS_PCT: 88},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cct:0", "brightness", 88)
    mock_rpc_device.mock_update()

    mock_rpc_device.cct_set.assert_called_once_with(0, {"on": True, "brightness": 88})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 224  # 88% of 255

    # Turn on, color temp = 4444 K
    mock_rpc_device.cct_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.COLOR_TEMP_KELVIN: 4444},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cct:0", "ct", 4444)

    mock_rpc_device.mock_update()

    mock_rpc_device.cct_set.assert_called_once_with(0, {"on": True, "ct": 4444})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 4444


async def test_rpc_remove_cct_light(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
) -> None:
    """Test Shelly RPC remove orphaned CCT light entity."""
    # register CCT light entity
    config_entry = await init_integration(hass, 2, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    register_entity(
        hass,
        LIGHT_DOMAIN,
        "cct_light_0",
        "cct:0",
        config_entry,
        device_id=device_entry.id,
    )

    # verify CCT light entity created
    assert get_entity(hass, LIGHT_DOMAIN, "cct:0") is not None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # there is no cct:0 in the status, so the CCT light entity should be removed
    assert get_entity(hass, LIGHT_DOMAIN, "cct:0") is None


async def test_rpc_cct_light_without_ct_range(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC CCT light without ct_range in the light config."""
    entity_id = f"{LIGHT_DOMAIN}.test_name_living_room_lamp"

    config = deepcopy(mock_rpc_device.config)
    config["cct:0"] = {"id": 0, "name": "Living room lamp"}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["cct:0"] = {"id": 0, "output": False, "brightness": 77, "ct": 3666}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # default values from constants are 2700 and 6500
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500


async def test_rpc_rgbcct_light(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC RGBCCT light."""
    entity_id = f"{LIGHT_DOMAIN}.test_name"

    config = deepcopy(mock_rpc_device.config)
    config["rgbcct:0"] = {"id": 0, "name": None}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["rgbcct:0"] = {
        "id": 0,
        "output": False,
        "brightness": 44,
        "ct": 3349,
        "rgb": [76, 140, 255],
        "mode": "cct",
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3, MODEL_MULTICOLOR_BULB_G3)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-rgbcct:0"

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.rgbcct_set.assert_called_once_with(0, {"on": False})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    # Turn on
    mock_rpc_device.rgbcct_set.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgbcct:0", "output", True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.rgbcct_set.assert_called_once_with(0, {"on": True})
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_BRIGHTNESS] == 112
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3349
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500

    # Turn on, brightness = 88
    mock_rpc_device.rgbcct_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS_PCT: 88},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgbcct:0", "brightness", 88)
    mock_rpc_device.mock_update()

    mock_rpc_device.rgbcct_set.assert_called_once_with(
        0, {"on": True, "brightness": 88}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 224  # 88% of 255

    # Turn on, color temp = 4444 K
    mock_rpc_device.rgbcct_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.COLOR_TEMP_KELVIN: 4444},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgbcct:0", "ct", 4444)
    mock_rpc_device.mock_update()

    mock_rpc_device.rgbcct_set.assert_called_once_with(
        0, {"on": True, "ct": 4444, "mode": "cct"}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 4444

    # Turn on, color 100, 150, 200
    mock_rpc_device.rgbcct_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: entity_id,
            LightServiceArgument.RGB_COLOR: [100, 150, 200],
        },
        blocking=True,
    )

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "rgbcct:0", "rgb", [100, 150, 200]
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "rgbcct:0", "mode", "rgb")
    mock_rpc_device.mock_update()

    mock_rpc_device.rgbcct_set.assert_called_once_with(
        0, {"on": True, "rgb": [100, 150, 200], "mode": "rgb"}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_RGB_COLOR] == (100, 150, 200)


async def test_rpc_ledstrip_light(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC LED strip light."""
    entity_id = LEDSTRIP_ENTITY_ID

    await init_integration(hass, 4)

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-state")

    entry = entity_registry.async_get(entity_id)
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(0, {"on": False})

    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "on", True
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(0, {"on": True})
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_BRIGHTNESS] == 92
    assert state.attributes[ATTR_RGB_COLOR] is None
    assert state.attributes[ATTR_EFFECT] == "rainbow"

    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.BRIGHTNESS_PCT: 88},
        blocking=True,
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "brightness", 88
    )
    mock_ledstrip_rpc_device.mock_update()

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "brightness": 88}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 224  # 88% of 255

    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: entity_id,
            LightServiceArgument.EFFECT: "solid",
            LightServiceArgument.RGB_COLOR: [100, 150, 200],
        },
        blocking=True,
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "effect", "solid"
    )
    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "rgb", [100, 150, 200]
    )
    mock_ledstrip_rpc_device.mock_update()

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0,
        {"on": True, "rgb": [100, 150, 200], "effect": "solid"},
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "solid"
    assert state.attributes[ATTR_RGB_COLOR] == (100, 150, 200)

    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id, LightServiceArgument.EFFECT: "fade"},
        blocking=True,
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "effect", "fade"
    )
    mock_ledstrip_rpc_device.mock_update()

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "effect": "fade"}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "fade"


async def test_rpc_ledstrip_light_device_not_initialized(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC LED strip light state update when the device is not initialized."""
    entity_id = LEDSTRIP_ENTITY_ID

    await init_integration(hass, 4)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_EFFECT_LIST] == list(MOCK_LEDSTRIP_EFFECTS)

    monkeypatch.setattr(mock_ledstrip_rpc_device, "initialized", False)
    mock_ledstrip_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_EFFECT_LIST] == []


async def test_rpc_ledstrip_background_light(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC LED strip effect background light."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status,
        "ledstrip:0",
        MOCK_LEDSTRIP_STATUS_BLINK | {"on": True},
    )

    await init_integration(hass, 4)

    state = hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID)
    assert state == snapshot(name=f"{LEDSTRIP_BACKGROUND_ENTITY_ID}-state")

    entry = entity_registry.async_get(LEDSTRIP_BACKGROUND_ENTITY_ID)
    assert entry == snapshot(name=f"{LEDSTRIP_BACKGROUND_ENTITY_ID}-entry")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID,
            LightServiceArgument.RGB_COLOR: [100, 150, 200],
            LightServiceArgument.BRIGHTNESS: 128,
        },
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "bg_rgb": [64, 96, 128]}
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "bg_rgb", [64, 96, 128]
    )
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (128, 191, 255)

    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"bg_rgb": [0, 0, 0]}
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "bg_rgb", [0, 0, 0]
    )
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID))
    assert state.state == STATE_OFF

    # Turning on without a color or brightness restores the last background color
    mock_ledstrip_rpc_device.ledstrip_set.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "bg_rgb": [64, 96, 128]}
    )


async def test_rpc_ledstrip_background_light_turn_on_default_white(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the background light turns on white without a color to restore."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status,
        "ledstrip:0",
        MOCK_LEDSTRIP_STATUS_AURORA | {"on": True},
    )

    await init_integration(hass, 4)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "bg_rgb": [255, 255, 255]}
    )


async def test_rpc_ledstrip_background_light_turn_on_strip_off(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test turning on the background light also turns on the LED strip."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status, "ledstrip:0", MOCK_LEDSTRIP_STATUS_BLINK
    )

    await init_integration(hass, 4)

    assert (state := hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID))
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID},
        blocking=True,
    )

    # The background color stored for the effect is kept
    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(
        0, {"on": True, "bg_rgb": [171, 171, 171]}
    )

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", "on", True
    )
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID))
    assert state.state == STATE_ON


async def test_rpc_ledstrip_background_light_turn_off_strip_off(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test turning off the background light keeps its color if the strip is off."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status, "ledstrip:0", MOCK_LEDSTRIP_STATUS_BLINK
    )

    await init_integration(hass, 4)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: LEDSTRIP_BACKGROUND_ENTITY_ID},
        blocking=True,
    )

    mock_ledstrip_rpc_device.ledstrip_set.assert_not_called()


@pytest.mark.parametrize(
    ("ledstrip_status", "expected_state"),
    [
        pytest.param(
            MOCK_LEDSTRIP_STATUS_BLINK | {"on": True}, STATE_ON, id="background_set"
        ),
        pytest.param(MOCK_LEDSTRIP_STATUS_BLINK, STATE_OFF, id="main_light_off"),
        pytest.param(
            MOCK_LEDSTRIP_STATUS_AURORA | {"on": True},
            STATE_OFF,
            id="background_black",
        ),
        pytest.param(
            MOCK_LEDSTRIP_STATUS_RAINBOW, STATE_UNAVAILABLE, id="no_background"
        ),
    ],
)
async def test_rpc_ledstrip_background_light_availability(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    ledstrip_status: dict[str, Any],
    expected_state: str,
) -> None:
    """Test RPC LED strip background light availability depends on the effect."""
    monkeypatch.setitem(mock_ledstrip_rpc_device.status, "ledstrip:0", ledstrip_status)

    await init_integration(hass, 4)

    assert (state := hass.states.get(LEDSTRIP_BACKGROUND_ENTITY_ID))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("ledstrip_status", "expected_rgb"),
    [
        pytest.param(MOCK_LEDSTRIP_STATUS_SOLID, (255, 81, 68), id="main_only"),
        pytest.param(MOCK_LEDSTRIP_STATUS_BLINK, (127, 172, 255), id="both"),
        pytest.param(
            MOCK_LEDSTRIP_STATUS_AURORA | {"rgb": [1, 2, 3]},
            None,
            id="background_only",
        ),
        pytest.param(MOCK_LEDSTRIP_STATUS_RAINBOW, None, id="none"),
    ],
)
async def test_rpc_ledstrip_light_color_by_effect(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    ledstrip_status: dict[str, Any],
    expected_rgb: tuple[int, int, int] | None,
) -> None:
    """Test RPC LED strip light reports a color only if the effect uses it."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status, "ledstrip:0", ledstrip_status | {"on": True}
    )

    await init_integration(hass, 4)

    assert (state := hass.states.get(LEDSTRIP_ENTITY_ID))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == expected_rgb


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param({}, id="current_effect"),
        pytest.param({LightServiceArgument.EFFECT: "aurora"}, id="new_effect"),
    ],
)
async def test_rpc_ledstrip_light_color_not_used_by_effect(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    service_data: dict[str, Any],
) -> None:
    """Test RPC LED strip light rejects a color the target effect does not use."""
    await init_integration(hass, 4)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            LightService.TURN_ON,
            {
                TargetKey.ENTITY_ID: LEDSTRIP_ENTITY_ID,
                LightServiceArgument.RGB_COLOR: [100, 150, 200],
                **service_data,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "ledstrip_effect_no_color"
    mock_ledstrip_rpc_device.call_rpc.assert_not_called()
