"""Tests for light platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

from flux_led.const import (
    COLOR_MODE_ADDRESSABLE as FLUX_COLOR_MODE_ADDRESSABLE,
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_DIM as FLUX_COLOR_MODE_DIM,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
    COLOR_MODE_RGBW as FLUX_COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW as FLUX_COLOR_MODE_RGBWW,
    COLOR_MODES_RGB_W as FLUX_COLOR_MODES_RGB_W,
    MODE_MUSIC,
    MultiColorEffects,
    WhiteChannelType,
)
from flux_led.protocol import MusicMode
import pytest

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import (
    CONF_COLORS,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    CONF_WHITE_CHANNEL_TYPE,
    DOMAIN,
    MIN_CCT_BRIGHTNESS,
    MIN_RGB_BRIGHTNESS,
    TRANSITION_JUMP,
)
from homeassistant.components.flux_led.light import (
    ATTR_BACKGROUND_COLOR,
    ATTR_FOREGROUND_COLOR,
    ATTR_LIGHT_SCREEN,
    ATTR_SENSITIVITY,
)
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
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EFFECT,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
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
    async_mock_device_turn_off,
    async_mock_device_turn_on,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_light_goes_unavailable_and_recovers(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light goes unavailable and then recovers."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    now = utcnow()
    bulb.async_update = AsyncMock(side_effect=RuntimeError)
    for i in range(10, 50, 10):
        async_fire_time_changed(hass, now + timedelta(seconds=i))
        await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    bulb.async_update = AsyncMock()
    for i in range(60, 100, 10):
        async_fire_time_changed(hass, now + timedelta(seconds=i))
        await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_light_mac_address_not_found(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light when we cannot discover the mac address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"
    assert entity_registry.async_get(entity_id).unique_id == config_entry.entry_id
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("protocol", "sw_version", "model_num", "model"),
    [
        ("LEDENET_ORIGINAL", 1, 0x01, "Original LEDEDNET (0x35)"),
        ("LEDENET", 8, 0x33, "Magic Home Branded RGB Controller (0x33)"),
    ],
)
async def test_light_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    protocol: str,
    sw_version: int,
    model_num: int,
    model: str,
) -> None:
    """Test a light device registry entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.version_num = sw_version
    bulb.protocol = protocol
    bulb.model_num = model_num
    bulb.model = model

    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    )
    assert device.sw_version == str(sw_version)
    assert device.model == model


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
    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_OFF

    bulb.brightness = 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (10, 10, 30)},
        blocking=True,
    )
    # If the bulb is off and we are using existing brightness
    # it has to be at least 1 or the bulb won't turn on
    bulb.async_set_levels.assert_called_with(10, 10, 30, brightness=1)
    bulb.async_set_levels.reset_mock()
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    # If its off and the device requires the turn on
    # command before setting brightness we need to make sure its called
    bulb.async_turn_on.assert_called_once()
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()
    await async_mock_device_turn_on(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (10, 10, 30)},
        blocking=True,
    )
    # If the bulb is on and we are using existing brightness
    # and brightness was 0 older devices will not be able to turn on
    # so we need to make sure its at least 1 and that we
    # call it before the turn on command since the device
    # does not support auto on
    bulb.async_set_levels.assert_called_with(10, 10, 30, brightness=1)
    bulb.async_set_levels.reset_mock()

    bulb.brightness = 128
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, brightness=128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()


async def test_rgb_light_auto_on(hass: HomeAssistant) -> None:
    """Test an rgb light that does not need the turn on command sent."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.requires_turn_on = False
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_OFF

    bulb.brightness = 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (10, 10, 30)},
        blocking=True,
    )
    # If the bulb is off and we are using existing brightness
    # it has to be at least 1 or the bulb won't turn on
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(10, 10, 30, brightness=1)
    bulb.async_set_levels.reset_mock()
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (0, 0, 0)},
        blocking=True,
    )
    # If the bulb is off and we are using existing brightness
    # it has to be at least 1 or the bulb won't turn on
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(
        MIN_RGB_BRIGHTNESS,
        MIN_RGB_BRIGHTNESS,
        MIN_RGB_BRIGHTNESS,
        brightness=MIN_RGB_BRIGHTNESS,
    )
    bulb.async_set_levels.reset_mock()
    bulb.async_turn_on.reset_mock()

    # Should still be called with no kwargs
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    await async_mock_device_turn_on(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_ON
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (10, 10, 30)},
        blocking=True,
    )
    # If the bulb is on and we are using existing brightness
    # and brightness was 0 we need to set it to at least 1
    # or the device may not turn on
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_not_called()
    bulb.async_set_levels.assert_called_with(10, 10, 30, brightness=1)
    bulb.async_set_levels.reset_mock()

    bulb.brightness = 128
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(255, 191, 178, brightness=128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()


async def test_rgbw_light_auto_on(hass: HomeAssistant) -> None:
    """Test an rgbw light that does not need the turn on command sent."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.requires_turn_on = False
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model
    bulb.color_modes = {FLUX_COLOR_MODE_RGBW}
    bulb.color_mode = FLUX_COLOR_MODE_RGBW
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGBW
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBW]
    assert attributes[ATTR_HS_COLOR] == (0.0, 83.529)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_OFF

    bulb.brightness = 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (10, 10, 30, 0)},
        blocking=True,
    )
    # If the bulb is off and we are using existing brightness
    # it has to be at least 1 or the bulb won't turn on
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(10, 10, 30, 0)
    bulb.async_set_levels.reset_mock()
    bulb.async_turn_on.reset_mock()

    # Should still be called with no kwargs
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    await async_mock_device_turn_on(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_ON
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (0, 0, 0, 0)},
        blocking=True,
    )
    # If the bulb is on and we are using existing brightness
    # and brightness was 0 we need to set it to at least 1
    # or the device may not turn on. In this case we scale
    # the current color to brightness of 1 to ensure the device
    # does not switch to white since otherwise we do not have
    # enough resolution to determine which color to display
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_not_called()
    bulb.async_set_levels.assert_called_with(2, 0, 0, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (0, 0, 0, 56)},
        blocking=True,
    )
    # If the bulb is on and we are using existing brightness
    # and brightness was 0 we need to set it to at least 1
    # or the device may not turn on. In this case we scale
    # the current color to brightness of 1 to ensure the device
    # does not switch to white since otherwise we do not have
    # enough resolution to determine which color to display
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_not_called()
    bulb.async_set_levels.assert_called_with(2, 0, 0, 56)
    bulb.async_set_levels.reset_mock()

    bulb.brightness = 128
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(110, 19, 0, 255)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()


async def test_rgbww_light_auto_on(hass: HomeAssistant) -> None:
    """Test an rgbww light that does not need the turn on command sent."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.requires_turn_on = False
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model
    bulb.color_modes = {FLUX_COLOR_MODE_RGBWW}
    bulb.color_mode = FLUX_COLOR_MODE_RGBWW
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == ColorMode.RGBWW
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGBWW]
    assert attributes[ATTR_HS_COLOR] == (3.237, 94.51)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_OFF

    bulb.brightness = 0
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (10, 10, 30, 0, 0)},
        blocking=True,
    )
    # If the bulb is off and we are using existing brightness
    # it has to be at least 1 or the bulb won't turn on
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(10, 10, 30, 0, 0)
    bulb.async_set_levels.reset_mock()
    bulb.async_turn_on.reset_mock()

    # Should still be called with no kwargs
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    await async_mock_device_turn_on(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_ON
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (0, 0, 0, 0, 0)},
        blocking=True,
    )
    # If the bulb is on and we are using existing brightness
    # and brightness was 0 we need to set it to at least 1
    # or the device may not turn on. In this case we scale
    # the current color so we do not unexpectedly switch to white
    # since other we do not have enough resolution to determine
    # which color to display
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_brightness.assert_not_called()
    bulb.async_set_levels.assert_called_with(2, 0, 0, 0, 0)
    bulb.async_set_levels.reset_mock()

    bulb.brightness = 128
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_levels.assert_called_with(14, 0, 30, 255, 255)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_turn_on.assert_not_called()
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()


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
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, brightness=128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()
    bulb.color_mode = FLUX_COLOR_MODE_CCT
    bulb.getWhiteTemperature = Mock(return_value=(5000, 128))
    bulb.color_temp = 5000

    bulb.raw_state = bulb.raw_state._replace(
        red=0, green=0, blue=0, warm_white=1, cool_white=2
    )
    await async_mock_device_turn_on(hass, bulb)
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
    bulb.async_set_white_temp.assert_called_with(2702, 128)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(255)
    bulb.async_set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(128)
    bulb.async_set_brightness.reset_mock()


async def test_rgbw_light_cold_white(hass: HomeAssistant) -> None:
    """Test an rgbw light with a cold white channel."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
            CONF_WHITE_CHANNEL_TYPE: WhiteChannelType.COLD.name.lower(),
        },
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGBW}
    bulb.color_mode = FLUX_COLOR_MODE_RGBW
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbw"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbw"]
    assert attributes[ATTR_RGB_COLOR] == (255, 42, 42)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()
    bulb.is_on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()
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
    bulb.async_set_levels.assert_called_with(128, 128, 128, 128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 255, 255, 255)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 191, 178, 0)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 100)
    bulb.async_set_effect.reset_mock()


async def test_rgbw_light_warm_white(hass: HomeAssistant) -> None:
    """Test an rgbw light with a warm white channel."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
            CONF_WHITE_CHANNEL_TYPE: WhiteChannelType.WARM.name.lower(),
        },
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGBW, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGBW
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbw"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgbw"]
    assert attributes[ATTR_RGB_COLOR] == (255, 42, 42)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()
    bulb.is_on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()
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
    bulb.async_set_levels.assert_called_with(128, 128, 128, 128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 255, 255, 255)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 191, 178, 0)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(6493, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(6493, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 290},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(3448, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (255, 191, 178, 0)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 100)
    bulb.async_set_effect.reset_mock()


async def test_rgb_or_w_light(hass: HomeAssistant) -> None:
    """Test an rgb or w light."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = FLUX_COLOR_MODES_RGB_W
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb", "white"]
    assert attributes[ATTR_RGB_COLOR] == (255, 0, 0)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()
    bulb.is_on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: (255, 255, 255),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 255, 255, brightness=128)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 100)
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_WHITE: 128,
        },
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(w=128)
    bulb.async_set_levels.reset_mock()

    bulb.color_mode = FLUX_COLOR_MODE_DIM

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_BRIGHTNESS: 100,
        },
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()


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
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbww"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "rgbww"]
    assert attributes[ATTR_HS_COLOR] == (3.237, 94.51)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()
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
    bulb.async_set_levels.assert_called_with(192, 192, 192, 192, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (255, 255, 255, 255, 50)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 255, 255, 50, 255)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(6493, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 154, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(6493, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 290},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(3448, 255)
    bulb.async_set_white_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (255, 191, 178, 0, 0)},
        blocking=True,
    )
    bulb.async_set_levels.assert_called_with(255, 191, 178, 0, 0)
    bulb.async_set_levels.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "random"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_once()
    bulb.async_set_effect.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "purple_fade"},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("purple_fade", 50, 50)
    bulb.async_set_effect.reset_mock()
    bulb.effect = "purple_fade"
    bulb.brightness = 128

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(255)
    bulb.async_set_brightness.reset_mock()

    await async_mock_device_turn_off(hass, bulb)
    bulb.color_mode = FLUX_COLOR_MODE_RGBWW
    bulb.brightness = MIN_RGB_BRIGHTNESS
    bulb.rgb = (MIN_RGB_BRIGHTNESS, MIN_RGB_BRIGHTNESS, MIN_RGB_BRIGHTNESS)
    await async_mock_device_turn_on(hass, bulb)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGBWW
    assert state.attributes[ATTR_BRIGHTNESS] == 1

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 170},
        blocking=True,
    )
    bulb.async_set_white_temp.assert_called_with(5882, MIN_CCT_BRIGHTNESS)
    bulb.async_set_white_temp.reset_mock()


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
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "brightness"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]
    assert ATTR_EFFECT_LIST in attributes  # single channel now supports effects

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.async_set_brightness.assert_called_with(100)
    bulb.async_set_brightness.reset_mock()


async def test_no_color_modes(hass: HomeAssistant) -> None:
    """Test a light that has no color modes defined in the database."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.mode = "ww"
    bulb.protocol = None
    bulb.color_modes = set()
    bulb.color_mode = None
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_COLOR_MODE] == "onoff"
    assert ATTR_EFFECT_LIST in attributes  # single channel now supports effects

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)

    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()


async def test_rgb_light_custom_effects(hass: HomeAssistant) -> None:
    """Test an rgb light with a custom effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
        options={
            CONF_MODE: "auto",
            CONF_CUSTOM_EFFECT_COLORS: "[0,0,255], [255,0,0]",
            CONF_CUSTOM_EFFECT_SPEED_PCT: 88,
            CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
        },
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == [*bulb.effect_list, "custom"]
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()
    await async_mock_device_turn_off(hass, bulb)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "custom"},
        blocking=True,
    )
    bulb.effect = "custom"
    bulb.async_set_custom_pattern.assert_called_with(
        [[0, 0, 255], [255, 0, 0]], 88, "jump"
    )
    bulb.async_set_custom_pattern.reset_mock()
    await async_mock_device_turn_on(hass, bulb)

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
    bulb.effect = "custom"
    bulb.async_set_custom_pattern.assert_called_with(
        [[0, 0, 255], [255, 0, 0]], 88, "jump"
    )
    bulb.async_set_custom_pattern.reset_mock()
    await async_mock_device_turn_on(hass, bulb)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == "custom"


@pytest.mark.parametrize("effect_colors", [":: CANNOT BE PARSED ::", None])
async def test_rgb_light_custom_effects_invalid_colors(
    hass: HomeAssistant, effect_colors: str
) -> None:
    """Test an rgb light with a invalid effect."""
    options = {
        CONF_MODE: "auto",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 88,
        CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
    }
    if effect_colors:
        options[CONF_CUSTOM_EFFECT_COLORS] = effect_colors
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        options=options,
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
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
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgb"
    assert attributes[ATTR_EFFECT_LIST] == bulb.effect_list
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
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
    bulb.async_set_custom_pattern.assert_called_with(
        [(0, 0, 255), (255, 0, 0)], 30, "jump"
    )
    bulb.async_set_custom_pattern.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_zones",
        {
            ATTR_ENTITY_ID: entity_id,
            CONF_COLORS: [[0, 0, 255], [255, 0, 0]],
            CONF_EFFECT: "running_water",
        },
        blocking=True,
    )
    bulb.async_set_zones.assert_called_with(
        [(0, 0, 255), (255, 0, 0)], 50, MultiColorEffects.RUNNING_WATER
    )
    bulb.async_set_zones.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_zones",
        {
            ATTR_ENTITY_ID: entity_id,
            CONF_COLORS: [[0, 0, 255], [255, 0, 0]],
            CONF_SPEED_PCT: 30,
        },
        blocking=True,
    )
    bulb.async_set_zones.assert_called_with(
        [(0, 0, 255), (255, 0, 0)], 30, MultiColorEffects.STATIC
    )
    bulb.async_set_zones.reset_mock()


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
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_COLOR_MODE] == "onoff"
    assert ATTR_EFFECT_LIST in attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_off.assert_called_once()

    await async_mock_device_turn_off(hass, bulb)
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.async_turn_on.assert_called_once()
    bulb.async_turn_on.reset_mock()
    await async_mock_device_turn_on(hass, bulb)


async def test_music_mode_service(hass: HomeAssistant) -> None:
    """Test music mode service."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0xA3)  # has music mode
    bulb.microphone = True
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.bulb_rgbcw_ddeeff"
    assert hass.states.get(entity_id)

    bulb.effect = MODE_MUSIC
    bulb.is_on = False
    await hass.services.async_call(
        DOMAIN,
        "set_music_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EFFECT: 12,
            ATTR_LIGHT_SCREEN: True,
            ATTR_SENSITIVITY: 50,
            ATTR_BRIGHTNESS: 50,
            ATTR_FOREGROUND_COLOR: [255, 0, 0],
            ATTR_BACKGROUND_COLOR: [0, 255, 0],
        },
        blocking=True,
    )
    bulb.async_set_music_mode.assert_called_once_with(
        sensitivity=50,
        brightness=50,
        mode=MusicMode.LIGHT_SCREEN.value,
        effect=12,
        foreground_color=(255, 0, 0),
        background_color=(0, 255, 0),
    )
