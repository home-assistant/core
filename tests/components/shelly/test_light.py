"""Tests for Shelly light platform."""
from unittest.mock import AsyncMock

from aioshelly.const import (
    MODEL_BULB,
    MODEL_BULB_RGBW,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_DUO,
    MODEL_RGBW2,
    MODEL_VINTAGE_V2,
)
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import init_integration, mutate_rpc_device_status
from .conftest import mock_white_light_set_state

RELAY_BLOCK_ID = 0
LIGHT_BLOCK_ID = 2


async def test_block_device_rgbw_bulb(
    hass: HomeAssistant, mock_block_device, entity_registry
) -> None:
    """Test block device RGBW bulb."""
    entity_id = "light.test_name_channel_1"
    await init_integration(hass, 1, model=MODEL_BULB)

    # Test initial
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_RGBW_COLOR] == (45, 55, 65, 70)
    assert attributes[ATTR_BRIGHTNESS] == 48
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGBW,
    ]
    assert attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.EFFECT
    assert len(attributes[ATTR_EFFECT_LIST]) == 7
    assert attributes[ATTR_EFFECT] == "Off"

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on, RGBW = [70, 80, 90, 20], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGBW_COLOR: [70, 80, 90, 30],
            ATTR_BRIGHTNESS: 33,
            ATTR_EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, white=30, effect=3
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGBW
    assert attributes[ATTR_RGBW_COLOR] == (70, 80, 90, 30)
    assert attributes[ATTR_BRIGHTNESS] == 33
    assert attributes[ATTR_EFFECT] == "Flash"

    # Turn on, COLOR_TEMP_KELVIN = 3500
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 3500

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-light_0"


async def test_block_device_rgb_bulb(
    hass: HomeAssistant,
    mock_block_device,
    monkeypatch,
    entity_registry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device RGB bulb."""
    entity_id = "light.test_name_channel_1"
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode")
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID], "description", "light_1"
    )
    await init_integration(hass, 1, model=MODEL_BULB_RGBW)

    # Test initial
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_RGB_COLOR] == (45, 55, 65)
    assert attributes[ATTR_BRIGHTNESS] == 48
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    ]
    assert (
        attributes[ATTR_SUPPORTED_FEATURES]
        == LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
    )
    assert len(attributes[ATTR_EFFECT_LIST]) == 4
    assert attributes[ATTR_EFFECT] == "Off"

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on, RGB = [70, 80, 90], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: [70, 80, 90],
            ATTR_BRIGHTNESS: 33,
            ATTR_EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, effect=3
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert attributes[ATTR_RGB_COLOR] == (70, 80, 90)
    assert attributes[ATTR_BRIGHTNESS] == 33
    assert attributes[ATTR_EFFECT] == "Flash"

    # Turn on, COLOR_TEMP_KELVIN = 3500
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 3500

    # Turn on with unsupported effect
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Breath"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", mode="color"
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_EFFECT] == "Off"
    assert "Effect 'Breath' not supported" in caplog.text

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-light_1"


async def test_block_device_white_bulb(
    hass: HomeAssistant,
    mock_block_device,
    entity_registry,
    monkeypatch,
) -> None:
    """Test block device white bulb."""
    entity_id = "light.test_name_channel_1"
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
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on, brightness = 33
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 33},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13
    )
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_BRIGHTNESS] == 33

    entry = entity_registry.async_get(entity_id)
    assert entry
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
    hass: HomeAssistant, mock_block_device, entity_registry, model, monkeypatch
) -> None:
    """Test block device supports transition."""
    entity_id = "light.test_name_channel_1"
    monkeypatch.setitem(
        mock_block_device.settings, "fw", "20220809-122808/v1.12-g99f7e0b"
    )
    monkeypatch.setattr(
        mock_block_device.blocks[LIGHT_BLOCK_ID], "description", "light_1"
    )
    await init_integration(hass, 1, model=model)

    # Test initial
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_FEATURES] & LightEntityFeature.TRANSITION

    # Turn on, TRANSITION = 4
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 4},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", transition=4000
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Turn off, TRANSITION = 6, limit to 5000ms
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 6},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off", transition=5000
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-light_1"


async def test_block_device_relay_app_type_light(
    hass: HomeAssistant, mock_block_device, entity_registry, monkeypatch
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
    state = hass.states.get(entity_id)
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Turn off
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="on"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-relay_1"


async def test_block_device_no_light_blocks(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device without light blocks."""
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("light.test_name_channel_1") is None


async def test_rpc_device_switch_type_lights_mode(
    hass: HomeAssistant, mock_rpc_device, entity_registry, monkeypatch
) -> None:
    """Test RPC device with switch in consumption type lights mode."""
    entity_id = "light.test_switch_0"
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    await init_integration(hass, 2)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "switch:0", "output", False)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-switch:0"


async def test_rpc_light(
    hass: HomeAssistant, mock_rpc_device, entity_registry, monkeypatch
) -> None:
    """Test RPC light."""
    entity_id = f"{LIGHT_DOMAIN}.test_light_0"
    monkeypatch.delitem(mock_rpc_device.status, "switch:0")
    await init_integration(hass, 2)

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.call_rpc.assert_called_once_with("Light.Set", {"id": 0, "on": True})
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 135

    # Turn off
    mock_rpc_device.call_rpc.reset_mock()
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", False)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.mock_update()
    mock_rpc_device.call_rpc.assert_called_once_with(
        "Light.Set", {"id": 0, "on": False}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on, brightness = 33
    mock_rpc_device.call_rpc.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 33},
        blocking=True,
    )

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", True)
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "brightness", 13)
    mock_rpc_device.mock_update()

    mock_rpc_device.call_rpc.assert_called_once_with(
        "Light.Set", {"id": 0, "on": True, "brightness": 13}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 33

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-light:0"
