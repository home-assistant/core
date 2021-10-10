"""Tests for light platform."""
from datetime import timedelta
from unittest.mock import Mock

from flux_led.const import (
    COLOR_MODE_ADDRESSABLE as FLUX_COLOR_MODE_ADDRESSABLE,
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_DIM as FLUX_COLOR_MODE_DIM,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
    COLOR_MODE_RGBW as FLUX_COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW as FLUX_COLOR_MODE_RGBWW,
)
import pytest

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import (
    CONF_COLORS,
    CONF_CUSTOM_EFFECT,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_DEVICES,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DOMAIN,
    MODE_AUTO,
    TRANSITION_JUMP,
)
from homeassistant.components.flux_led.light import EFFECT_CUSTOM_CODE, FLUX_EFFECT_LIST
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PROTOCOL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_light_no_unique_id(hass: HomeAssistant) -> None:
    """Test a light without a unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id) is None
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "protocol,sw_version,model", [("LEDENET_ORIGINAL", 1, 0x35), ("LEDENET", 8, 0x33)]
)
async def test_light_device_registry(
    hass: HomeAssistant, protocol: str, sw_version: int, model: int
) -> None:
    """Test a light device registry entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.protocol = protocol
    bulb.raw_state = bulb.raw_state._replace(model_num=model, version_number=sw_version)
    bulb.model_num = model

    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={}, connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    )
    assert device.sw_version == str(sw_version)
    assert device.model == f"0x{model:02X}"


async def test_rgb_light(hass: HomeAssistant) -> None:
    """Test an rgb light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 0, 0, brightness=100)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 191, 178, brightness=128)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.set_levels.assert_called_once()
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.setPresetPattern.assert_called_with(43, 50)
    bulb.setPresetPattern.reset_mock()

    with pytest.raises(ValueError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "does not exist"},
            blocking=True,
        )


async def test_rgb_cct_light(hass: HomeAssistant) -> None:
    """Test an rgb cct light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0x35)  # RGB & CCT model
    bulb.color_modes = {FLUX_COLOR_MODE_RGB, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 0, 0, brightness=100)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 191, 178, brightness=128)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.set_levels.assert_called_once()
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.setPresetPattern.assert_called_with(43, 50)
    bulb.setPresetPattern.reset_mock()

    bulb.is_on = True
    bulb.color_mode = FLUX_COLOR_MODE_CCT
    bulb.getWhiteTemperature = Mock(return_value=(5000, 128))
    bulb.raw_state = bulb.raw_state._replace(
        red=0, green=0, blue=0, warm_white=1, cool_white=2
    )
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "color_temp"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgb"]
    assert attributes[ATTR_COLOR_TEMP] == 200

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 370},
        blocking=True,
    )
    bulb.setWhiteTemperature.assert_called_with(2702, 128)
    bulb.setWhiteTemperature.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.setWhiteTemperature.assert_called_with(5000, 255)
    bulb.setWhiteTemperature.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    bulb.setWhiteTemperature.assert_called_with(5000, 128)
    bulb.setWhiteTemperature.reset_mock()


async def test_rgbw_light(hass: HomeAssistant) -> None:
    """Test an rgbw light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGBW}
    bulb.color_mode = FLUX_COLOR_MODE_RGBW
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbw"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbw"]
    assert attributes[ATTR_RGB_COLOR] == (255, 42, 42)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()
    bulb.is_on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(168, 0, 0, 33)
    bulb.set_levels.reset_mock()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGBW_COLOR: (255, 255, 255, 255),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    bulb.set_levels.assert_called_with(128, 128, 128, 128)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 255, 255, 255)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 191, 178, 0)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 191, 178, 0)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.set_levels.assert_called_once()
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.setPresetPattern.assert_called_with(43, 50)
    bulb.setPresetPattern.reset_mock()


async def test_rgbcw_light(hass: HomeAssistant) -> None:
    """Test an rgbcw light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(warm_white=1, cool_white=2)
    bulb.color_modes = {FLUX_COLOR_MODE_RGBWW, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGBWW
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbww"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgbww"]
    assert attributes[ATTR_HS_COLOR] == (3.237, 94.51)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(250, 0, 0, 49, 0)
    bulb.set_levels.reset_mock()
    bulb.is_on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGBWW_COLOR: (255, 255, 255, 0, 255),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    bulb.set_levels.assert_called_with(192, 192, 192, 192, 0)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (255, 255, 255, 255, 50)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 255, 255, 50, 255)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(r=0, b=0, g=0, w=0, w2=127)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(r=0, b=0, g=0, w=0, w2=255)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 290},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(r=0, b=0, g=0, w=102, w2=25)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (255, 191, 178, 0, 0)},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(255, 191, 178, 0, 0)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.set_levels.assert_called_once()
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.setPresetPattern.assert_called_with(43, 50)
    bulb.setPresetPattern.reset_mock()


async def test_white_light(hass: HomeAssistant) -> None:
    """Test a white light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.mode = "ww"
    bulb.protocol = None
    bulb.color_modes = {FLUX_COLOR_MODE_DIM}
    bulb.color_mode = FLUX_COLOR_MODE_DIM
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "white"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["white"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(w=100)
    bulb.set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_WHITE: 100},
        blocking=True,
    )
    bulb.set_levels.assert_called_with(w=100)
    bulb.set_levels.reset_mock()


async def test_rgb_light_custom_effects(hass: HomeAssistant) -> None:
    """Test an rgb light with a custom effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
        options={
            CONF_MODE: MODE_AUTO,
            CONF_CUSTOM_EFFECT_COLORS: "[0,0,255], [255,0,0]",
            CONF_CUSTOM_EFFECT_SPEED_PCT: 88,
            CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
        },
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == [*FLUX_EFFECT_LIST, "custom"]
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "custom"},
        blocking=True,
    )
    bulb.setCustomPattern.assert_called_with([[0, 0, 255], [255, 0, 0]], 88, "jump")
    bulb.setCustomPattern.reset_mock()
    bulb.raw_state = bulb.raw_state._replace(preset_pattern=EFFECT_CUSTOM_CODE)
    bulb.is_on = True
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == "custom"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 55, ATTR_EFFECT: "custom"},
        blocking=True,
    )
    bulb.setCustomPattern.assert_called_with([[0, 0, 255], [255, 0, 0]], 88, "jump")
    bulb.setCustomPattern.reset_mock()
    bulb.raw_state = bulb.raw_state._replace(preset_pattern=EFFECT_CUSTOM_CODE)
    bulb.is_on = True
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == "custom"


async def test_rgb_light_custom_effects_invalid_colors(hass: HomeAssistant) -> None:
    """Test an rgb light with a invalid effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
        options={
            CONF_MODE: MODE_AUTO,
            CONF_CUSTOM_EFFECT_COLORS: ":: CANNOT BE PARSED ::",
            CONF_CUSTOM_EFFECT_SPEED_PCT: 88,
            CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
        },
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)


async def test_rgb_light_custom_effect_via_service(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an rgb light with a custom effect set via the service."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == [*FLUX_EFFECT_LIST]
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        DOMAIN,
        "set_custom_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            CONF_COLORS: [[0, 0, 255], [255, 0, 0]],
            CONF_SPEED_PCT: 30,
            CONF_TRANSITION: "jump",
        },
        blocking=True,
    )
    bulb.setCustomPattern.assert_called_with([(0, 0, 255), (255, 0, 0)], 30, "jump")
    bulb.setCustomPattern.reset_mock()


async def test_migrate_from_yaml(hass: HomeAssistant) -> None:
    """Test migrate from yaml."""
    config = {
        LIGHT_DOMAIN: [
            {
                CONF_PLATFORM: DOMAIN,
                CONF_DEVICES: {
                    IP_ADDRESS: {
                        CONF_NAME: "flux_lamppost",
                        CONF_PROTOCOL: "ledenet",
                        CONF_CUSTOM_EFFECT: {
                            CONF_SPEED_PCT: 30,
                            CONF_TRANSITION: "strobe",
                            CONF_COLORS: [[255, 0, 0], [255, 255, 0], [0, 255, 0]],
                        },
                    }
                },
            }
        ],
    }
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, LIGHT_DOMAIN, config)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries

    migrated_entry = None
    for entry in entries:
        if entry.unique_id == MAC_ADDRESS:
            migrated_entry = entry
            break

    assert migrated_entry is not None
    assert migrated_entry.data == {
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: "flux_lamppost",
        CONF_PROTOCOL: "ledenet",
    }
    assert migrated_entry.options == {
        CONF_MODE: "auto",
        CONF_CUSTOM_EFFECT_COLORS: "[(255, 0, 0), (255, 255, 0), (0, 255, 0)]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
        CONF_CUSTOM_EFFECT_TRANSITION: "strobe",
    }


async def test_addressable_light(hass: HomeAssistant) -> None:
    """Test an addressable light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model
    bulb.color_modes = {FLUX_COLOR_MODE_ADDRESSABLE}
    bulb.color_mode = FLUX_COLOR_MODE_ADDRESSABLE
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_COLOR_MODE] == "onoff"
    assert attributes[ATTR_EFFECT_LIST] == FLUX_EFFECT_LIST
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()
    bulb.is_on = True

    with pytest.raises(ValueError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
            blocking=True,
        )
