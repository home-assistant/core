"""Tests for Shelly light platform."""
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

RELAY_BLOCK_ID = 0
LIGHT_BLOCK_ID = 2


async def test_block_device_rgbw_bulb(hass: HomeAssistant, mock_block_device) -> None:
    """Test block device RGBW bulb."""
    await init_integration(hass, 1, model="SHBLB-1")

    # Test initial
    state = hass.states.get("light.test_name_channel_1")
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
        {ATTR_ENTITY_ID: "light.test_name_channel_1"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_OFF

    # Turn on, RGBW = [70, 80, 90, 20], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_name_channel_1",
            ATTR_RGBW_COLOR: [70, 80, 90, 30],
            ATTR_BRIGHTNESS: 33,
            ATTR_EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, white=30, effect=3
    )
    state = hass.states.get("light.test_name_channel_1")
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
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 3500


async def test_block_device_rgb_bulb(
    hass: HomeAssistant,
    mock_block_device,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device RGB bulb."""
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode")
    await init_integration(hass, 1, model="SHCB-1")

    # Test initial
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_RGB_COLOR] == (45, 55, 65)
    assert attributes[ATTR_BRIGHTNESS] == 48
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    ]
    assert attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.EFFECT
    assert len(attributes[ATTR_EFFECT_LIST]) == 4
    assert attributes[ATTR_EFFECT] == "Off"

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_name_channel_1"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_OFF

    # Turn on, RGB = [70, 80, 90], brightness = 33, effect = Flash
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_name_channel_1",
            ATTR_RGB_COLOR: [70, 80, 90],
            ATTR_BRIGHTNESS: 33,
            ATTR_EFFECT: "Flash",
        },
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13, red=70, green=80, blue=90, effect=3
    )
    state = hass.states.get("light.test_name_channel_1")
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
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_COLOR_TEMP_KELVIN: 3500},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", temp=3500, mode="white"
    )
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 3500

    # Turn on with unsupported effect
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_EFFECT: "Breath"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", mode="color"
    )
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_EFFECT] == "Off"
    assert "Effect 'Breath' not supported" in caplog.text


async def test_block_device_white_bulb(
    hass: HomeAssistant,
    mock_block_device,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device white bulb."""
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "red")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "green")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "blue")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "colorTemp")
    monkeypatch.delattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "effect")
    await init_integration(hass, 1, model="SHVIN-1")

    # Test initial
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Turn off
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_name_channel_1"},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_OFF

    # Turn on, brightness = 33
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_BRIGHTNESS: 33},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", gain=13, brightness=13
    )
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_BRIGHTNESS] == 33


@pytest.mark.parametrize(
    "model",
    [
        "SHBDUO-1",
        "SHCB-1",
        "SHDM-1",
        "SHDM-2",
        "SHRGBW2",
        "SHVIN-1",
    ],
)
async def test_block_device_support_transition(
    hass: HomeAssistant, mock_block_device, model, monkeypatch
) -> None:
    """Test block device supports transition."""
    monkeypatch.setitem(
        mock_block_device.settings, "fw", "20220809-122808/v1.12-g99f7e0b"
    )
    await init_integration(hass, 1, model=model)

    # Test initial
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_FEATURES] & LightEntityFeature.TRANSITION

    # Turn on, TRANSITION = 4
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_TRANSITION: 4},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="on", transition=4000
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_ON

    # Turn off, TRANSITION = 6, limit to 5000ms
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_name_channel_1", ATTR_TRANSITION: 6},
        blocking=True,
    )
    mock_block_device.blocks[LIGHT_BLOCK_ID].set_state.assert_called_once_with(
        turn="off", transition=5000
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_OFF


async def test_block_device_relay_app_type_light(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device relay in app type set to light mode."""
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
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None

    # Test initial
    state = hass.states.get("light.test_name_channel_1")
    attributes = state.attributes
    assert state.state == STATE_ON
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Turn off
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_name_channel_1"},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="off"
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_OFF

    # Turn on
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_name_channel_1"},
        blocking=True,
    )
    mock_block_device.blocks[RELAY_BLOCK_ID].set_state.assert_called_once_with(
        turn="on"
    )
    state = hass.states.get("light.test_name_channel_1")
    assert state.state == STATE_ON


async def test_block_device_no_light_blocks(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device without light blocks."""
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("light.test_name_channel_1") is None


async def test_rpc_device_switch_type_lights_mode(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC device with switch in consumption type lights mode."""
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    await init_integration(hass, 2)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_switch_0"},
        blocking=True,
    )
    assert hass.states.get("light.test_switch_0").state == STATE_ON

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "switch:0", "output", False)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_switch_0"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("light.test_switch_0").state == STATE_OFF


async def test_rpc_light(hass: HomeAssistant, mock_rpc_device, monkeypatch) -> None:
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
