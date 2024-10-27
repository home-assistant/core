"""Tests for light platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory
from kasa import (
    AuthenticationError,
    DeviceType,
    KasaException,
    LightState,
    Module,
    TimeoutError,
)
from kasa.interfaces import LightEffect
from kasa.iot import IotDevice
import pytest

from homeassistant.components import tplink
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    DEVICE_ID,
    MAC_ADDRESS,
    _mocked_device,
    _patch_connect,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("device_type"),
    [
        pytest.param(DeviceType.Dimmer, id="Dimmer"),
        pytest.param(DeviceType.Bulb, id="Bulb"),
        pytest.param(DeviceType.LightStrip, id="LightStrip"),
        pytest.param(DeviceType.WallSwitch, id="WallSwitch"),
    ],
)
async def test_light_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, device_type
) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light = _mocked_device(modules=[Module.Light], alias="my_light")
    light.device_type = device_type
    with _patch_discovery(device=light), _patch_connect(device=light):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"
    assert (
        entity_registry.async_get(entity_id).unique_id
        == MAC_ADDRESS.replace(":", "").upper()
    )


async def test_legacy_dimmer_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light = _mocked_device(
        modules=[Module.Light],
        alias="my_light",
        spec=IotDevice,
        device_id="aa:bb:cc:dd:ee:ff",
    )
    light.device_type = DeviceType.Dimmer

    with _patch_discovery(device=light), _patch_connect(device=light):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("device", "transition"),
    [
        (_mocked_device(modules=[Module.Light]), 2.0),
        (_mocked_device(modules=[Module.Light, Module.LightEffect]), None),
    ],
)
async def test_color_light(
    hass: HomeAssistant, device: MagicMock, transition: float | None
) -> None:
    """Test a color light and that all transitions are correctly passed."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light = device.modules[Module.Light]
    light.color_temp = None
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    KASA_TRANSITION_VALUE = transition * 1_000 if transition is not None else None

    BASE_PAYLOAD = {ATTR_ENTITY_ID: entity_id}
    if transition:
        BASE_PAYLOAD[ATTR_TRANSITION] = transition

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]
    # If effect is active, only the brightness can be controlled
    if attributes.get(ATTR_EFFECT) is not None:
        assert attributes[ATTR_COLOR_MODE] == "brightness"
    else:
        assert attributes[ATTR_COLOR_MODE] == "hs"
        assert attributes[ATTR_MIN_MIREDS] == 111
        assert attributes[ATTR_MAX_MIREDS] == 250
        assert attributes[ATTR_HS_COLOR] == (10, 30)
        assert attributes[ATTR_RGB_COLOR] == (255, 191, 178)
        assert attributes[ATTR_XY_COLOR] == (0.42, 0.336)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", BASE_PAYLOAD, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(light_on=False, transition=KASA_TRANSITION_VALUE)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(LIGHT_DOMAIN, "turn_on", BASE_PAYLOAD, blocking=True)
    light.set_state.assert_called_once_with(
        LightState(light_on=True, transition=KASA_TRANSITION_VALUE)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=KASA_TRANSITION_VALUE)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=KASA_TRANSITION_VALUE
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=KASA_TRANSITION_VALUE
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    light.set_hsv.assert_called_with(10, 30, None, transition=KASA_TRANSITION_VALUE)
    light.set_hsv.reset_mock()


async def test_color_light_no_temp(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.is_variable_color_temp = False
    type(light).color_temp = PropertyMock(side_effect=Exception)
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "hs"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs"]
    assert attributes[ATTR_HS_COLOR] == (10, 30)
    assert attributes[ATTR_RGB_COLOR] == (255, 191, 178)
    assert attributes[ATTR_XY_COLOR] == (0.42, 0.336)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    light.set_hsv.assert_called_with(10, 30, None, transition=None)
    light.set_hsv.reset_mock()


@pytest.mark.parametrize(
    ("bulb", "is_color"),
    [
        (_mocked_device(modules=[Module.Light], alias="my_light"), True),
        (_mocked_device(modules=[Module.Light], alias="my_light"), False),
    ],
)
async def test_color_temp_light(
    hass: HomeAssistant, bulb: MagicMock, is_color: bool
) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.is_color = is_color
    light.color_temp = 4000
    light.is_variable_color_temp = True

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "color_temp"
    if light.is_color:
        assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]
    else:
        assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]
    assert attributes[ATTR_MIN_MIREDS] == 111
    assert attributes[ATTR_MAX_MIREDS] == 250
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 4000

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(6666, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 20000},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(9000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 1},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(4000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()


async def test_brightness_only_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.is_color = False
    light.is_variable_color_temp = False

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "brightness"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()


async def test_on_off_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.is_color = False
    light.is_variable_color_temp = False
    light.is_dimmable = False

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()


async def test_off_at_start_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.is_color = False
    light.is_variable_color_temp = False
    light.is_dimmable = False
    light.state = LightState(light_on=False)

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "off"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]


async def test_dimmer_turn_on_fix(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    device.device_type = DeviceType.Dimmer
    light.state = LightState(light_on=False)

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(
            light_on=True,
            brightness=None,
            hue=None,
            saturation=None,
            color_temp=None,
            transition=1,
        )
    )
    light.set_state.reset_mock()


async def test_smart_strip_effects(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test smart strip effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light = device.modules[Module.Light]
    light_effect = device.modules[Module.LightEffect]

    with (
        _patch_discovery(device=device),
        _patch_single_discovery(device=device),
        _patch_connect(device=device),
    ):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Effect1"
    assert state.attributes[ATTR_EFFECT_LIST] == ["Off", "Effect1", "Effect2"]

    # Ensure setting color temp when an effect
    # is in progress calls set_effect to clear the effect
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    light_effect.set_effect.assert_called_once_with(LightEffect.LIGHT_EFFECTS_OFF)
    light.set_color_temp.assert_called_once_with(4000, brightness=None, transition=None)
    light_effect.set_effect.reset_mock()
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Effect2"},
        blocking=True,
    )
    light_effect.set_effect.assert_called_once_with(
        "Effect2", brightness=None, transition=None
    )
    light_effect.set_effect.reset_mock()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Effect2"

    # Test setting light effect off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "off"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "off"
    light.set_state.assert_not_called()

    # Test setting light effect to invalid value
    caplog.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Effect3"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "off"
    assert "Invalid effect Effect3 for" in caplog.text

    light_effect.effect = LightEffect.LIGHT_EFFECTS_OFF
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == EFFECT_OFF

    light.state = LightState(light_on=False)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_EFFECT] is None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    light.state = LightState(light_on=True)
    light_effect.effect_list = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT_LIST] is None


async def test_smart_strip_custom_random_effect(hass: HomeAssistant) -> None:
    """Test smart strip custom random effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light = device.modules[Module.Light]
    light_effect = device.modules[Module.LightEffect]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "backgrounds": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
        },
        blocking=True,
    )
    light_effect.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 100,
            "backgrounds": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
        }
    )
    light_effect.set_custom_effect.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "random_seed": 600,
        },
        blocking=True,
    )
    light_effect.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 600,
        }
    )
    light_effect.set_custom_effect.reset_mock()

    light_effect.effect = {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": 100,
        "name": "Custom",
        "enable": 1,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    light.state = LightState(light_on=False)
    light_effect.effect = LightEffect.LIGHT_EFFECTS_OFF
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_EFFECT] is None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "backgrounds": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
            "random_seed": 50,
            "brightness": 80,
            "duration": 5000,
            "transition": 2000,
            "fadeoff": 3000,
            "hue_range": [0, 360],
            "saturation_range": [0, 100],
            "brightness_range": [0, 100],
            "transition_range": [2000, 3000],
        },
    )
    await hass.async_block_till_done()

    light_effect.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 80,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 5000,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 50,
            "backgrounds": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
            "fadeoff": 3000,
            "hue_range": [0, 360],
            "saturation_range": [0, 100],
            "brightness_range": [0, 100],
            "transition_range": [2000, 3000],
        }
    )
    light_effect.set_custom_effect.reset_mock()


async def test_smart_strip_custom_random_effect_at_start(hass: HomeAssistant) -> None:
    """Test smart strip custom random effects at startup."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light = device.modules[Module.Light]
    light_effect = device.modules[Module.LightEffect]
    light_effect.effect = LightEffect.LIGHT_EFFECTS_OFF
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    # fallback to set HSV when custom effect is not known so it does turn back on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()


async def test_smart_strip_custom_sequence_effect(hass: HomeAssistant) -> None:
    """Test smart strip custom sequence effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light_effect = device.modules[Module.LightEffect]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "sequence_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "sequence": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
        },
        blocking=True,
    )
    light_effect.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "sequence",
            "sequence": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
            "repeat_times": 0,
            "spread": 1,
            "direction": 4,
        }
    )
    light_effect.set_custom_effect.reset_mock()


@pytest.mark.parametrize(
    ("exception_type", "msg", "reauth_expected"),
    [
        (
            AuthenticationError,
            "Device authentication error async_turn_on: test error",
            True,
        ),
        (
            TimeoutError,
            "Timeout communicating with the device async_turn_on: test error",
            False,
        ),
        (
            KasaException,
            "Unable to communicate with the device async_turn_on: test error",
            False,
        ),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_light_errors_when_turned_on(
    hass: HomeAssistant,
    exception_type,
    msg,
    reauth_expected,
) -> None:
    """Tests the light wraps errors correctly."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    light.set_state.side_effect = exception_type(msg)

    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    assert not any(
        already_migrated_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    )

    with pytest.raises(HomeAssistantError, match=msg):
        await hass.services.async_call(
            LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    await hass.async_block_till_done()
    assert light.set_state.call_count == 1
    assert (
        any(
            flow
            for flow in already_migrated_config_entry.async_get_active_flows(
                hass, {SOURCE_REAUTH}
            )
            if flow["handler"] == tplink.DOMAIN
        )
        == reauth_expected
    )


async def test_light_child(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test child lights are added to parent device with the right ids."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    child_light_1 = _mocked_device(
        modules=[Module.Light], alias="my_light_0", device_id=f"{DEVICE_ID}00"
    )
    child_light_2 = _mocked_device(
        modules=[Module.Light], alias="my_light_1", device_id=f"{DEVICE_ID}01"
    )
    parent_device = _mocked_device(
        device_id=DEVICE_ID,
        alias="my_device",
        children=[child_light_1, child_light_2],
        modules=[Module.Light],
    )

    with _patch_discovery(device=parent_device), _patch_connect(device=parent_device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_device"
    entity = entity_registry.async_get(entity_id)
    assert entity

    for light_id in range(2):
        child_entity_id = f"light.my_device_my_light_{light_id}"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"{DEVICE_ID}0{light_id}"
        assert child_entity.device_id == entity.device_id


async def test_scene_effect_light(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activating a scene works with effects.

    i.e. doesn't try to set the effect to 'off'
    """
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light_effect = device.modules[Module.LightEffect]
    light_effect.effect = LightEffect.LIGHT_EFFECTS_OFF

    with _patch_discovery(device=device), _patch_connect(device=device):
        assert await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        assert await async_setup_component(hass, "scene", {})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    freezer.tick(5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state is STATE_ON
    assert state.attributes["effect"] is EFFECT_OFF

    await hass.services.async_call(
        "scene",
        "create",
        {"scene_id": "effect_off_scene", "snapshot_entities": [entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    scene_state = hass.states.get("scene.effect_off_scene")
    assert scene_state.state is STATE_UNKNOWN

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    freezer.tick(5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF

    await hass.services.async_call(
        "scene",
        "turn_on",
        {
            "entity_id": "scene.effect_off_scene",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    scene_state = hass.states.get("scene.effect_off_scene")
    assert scene_state.state is not STATE_UNKNOWN

    freezer.tick(5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state is STATE_ON
    assert state.attributes["effect"] is EFFECT_OFF
