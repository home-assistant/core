"""Tests for light platform."""

from __future__ import annotations

from datetime import timedelta
import re
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
from homeassistant.components.homeassistant.scene import (
    CONF_SCENE_ID,
    CONF_SNAPSHOT,
    SERVICE_CREATE,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.light import (
    SERVICE_RANDOM_EFFECT,
    SERVICE_SEQUENCE_EFFECT,
)
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
from homeassistant.util import dt as dt_util

from . import (
    _mocked_device,
    _mocked_feature,
    _patch_connect,
    _patch_discovery,
    _patch_single_discovery,
)
from .const import DEVICE_ID, MAC_ADDRESS

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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"
    assert (
        entity_registry.async_get(entity_id).unique_id
        == MAC_ADDRESS.replace(":", "").upper()
    )


async def test_legacy_dimmer_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dimmer unique id."""
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    assert entity_registry.async_get(entity_id).unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("device", "extra_data", "expected_transition"),
    [
        (
            _mocked_device(
                modules=[Module.Light],
                features=[
                    _mocked_feature("brightness", value=50),
                    _mocked_feature("hsv", value=(10, 30, 5)),
                    _mocked_feature(
                        "color_temp", value=4000, minimum_value=4000, maximum_value=9000
                    ),
                ],
            ),
            {ATTR_TRANSITION: 2.0},
            2.0 * 1_000,
        ),
        (
            _mocked_device(
                modules=[Module.Light],
                features=[
                    _mocked_feature("brightness", value=50),
                    _mocked_feature("hsv", value=(10, 30, 5)),
                    _mocked_feature(
                        "color_temp", value=4000, minimum_value=4000, maximum_value=9000
                    ),
                ],
            ),
            {},
            None,
        ),
    ],
)
async def test_color_light(
    hass: HomeAssistant,
    device: MagicMock,
    extra_data: dict,
    expected_transition: float | None,
) -> None:
    """Test a color light and that all transitions are correctly passed."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light = device.modules[Module.Light]

    # Setting color_temp to None emulates a device without color temp
    light.color_temp = None

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    BASE_PAYLOAD = {ATTR_ENTITY_ID: entity_id}
    BASE_PAYLOAD |= extra_data

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]

    assert attributes.get(ATTR_EFFECT) is None

    assert attributes[ATTR_COLOR_MODE] == "hs"
    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 4000
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 9000
    assert attributes[ATTR_HS_COLOR] == (10, 30)
    assert attributes[ATTR_RGB_COLOR] == (255, 191, 178)
    assert attributes[ATTR_XY_COLOR] == (0.42, 0.336)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, BASE_PAYLOAD, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(light_on=False, transition=expected_transition)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, BASE_PAYLOAD, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(light_on=True, transition=expected_transition)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=expected_transition)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=expected_transition
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=expected_transition
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    light.set_hsv.assert_called_with(10, 30, None, transition=expected_transition)
    light.set_hsv.reset_mock()


@pytest.mark.parametrize(
    ("device", "extra_data", "expected_transition"),
    [
        (
            _mocked_device(
                modules=[Module.Light, Module.LightEffect],
                features=[
                    _mocked_feature("brightness", value=50),
                    _mocked_feature("hsv", value=(10, 30, 5)),
                    _mocked_feature(
                        "color_temp", value=4000, minimum_value=4000, maximum_value=9000
                    ),
                ],
            ),
            {ATTR_TRANSITION: 2.0},
            2.0 * 1_000,
        ),
        (
            _mocked_device(
                modules=[Module.Light, Module.LightEffect],
                features=[
                    _mocked_feature("brightness", value=50),
                    _mocked_feature("hsv", value=(10, 30, 5)),
                    _mocked_feature(
                        "color_temp", value=4000, minimum_value=4000, maximum_value=9000
                    ),
                ],
            ),
            {},
            None,
        ),
    ],
)
async def test_color_light_with_active_effect(
    hass: HomeAssistant,
    device: MagicMock,
    extra_data: dict,
    expected_transition: float | None,
) -> None:
    """Test a color light and that all transitions are correctly passed."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light = device.modules[Module.Light]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    BASE_PAYLOAD = {ATTR_ENTITY_ID: entity_id}
    BASE_PAYLOAD |= extra_data

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]

    # If effect is active, only the brightness can be controlled
    assert attributes.get(ATTR_EFFECT) is not None
    assert attributes[ATTR_COLOR_MODE] == "brightness"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, BASE_PAYLOAD, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(light_on=False, transition=expected_transition)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, BASE_PAYLOAD, blocking=True
    )
    light.set_state.assert_called_once_with(
        LightState(light_on=True, transition=expected_transition)
    )
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=expected_transition)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=expected_transition
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(
        6666, brightness=None, transition=expected_transition
    )
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {**BASE_PAYLOAD, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    light.set_hsv.assert_called_with(10, 30, None, transition=expected_transition)
    light.set_hsv.reset_mock()


async def test_color_light_no_temp(hass: HomeAssistant) -> None:
    """Test a color light with no color temp."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    features = [
        _mocked_feature("brightness", value=50),
        _mocked_feature("hsv", value=(10, 30, 5)),
    ]

    device = _mocked_device(modules=[Module.Light], alias="my_light", features=features)
    light = device.modules[Module.Light]

    type(light).color_temp = PropertyMock(side_effect=Exception)
    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
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
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    light.set_hsv.assert_called_with(10, 30, None, transition=None)
    light.set_hsv.reset_mock()


async def test_color_temp_light_color(hass: HomeAssistant) -> None:
    """Test a color temp light with color."""
    device = _mocked_device(
        modules=[Module.Light],
        alias="my_light",
        features=[
            _mocked_feature("brightness", value=50),
            _mocked_feature("hsv", value=(10, 30, 5)),
            _mocked_feature(
                "color_temp", value=4000, minimum_value=4000, maximum_value=9000
            ),
        ],
    )
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    light = device.modules[Module.Light]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "color_temp"

    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(6666, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 20000},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(9000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 1},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(4000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()


async def test_color_temp_light_no_color(hass: HomeAssistant) -> None:
    """Test a color temp light with no color."""
    device = _mocked_device(
        modules=[Module.Light],
        alias="my_light",
        features=[
            _mocked_feature("brightness", value=50),
            _mocked_feature(
                "color_temp", value=4000, minimum_value=4000, maximum_value=9000
            ),
        ],
    )
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    light = device.modules[Module.Light]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "color_temp"

    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]
    assert attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 9000
    assert attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 4000
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 4000

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6666},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(6666, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 20000},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(9000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()

    # Verify color temp is clamped to the valid range
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 1},
        blocking=True,
    )
    light.set_color_temp.assert_called_with(4000, brightness=None, transition=None)
    light.set_color_temp.reset_mock()


async def test_brightness_only_light(hass: HomeAssistant) -> None:
    """Test a light brightness."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    features = [
        _mocked_feature("brightness", value=50),
    ]
    device = _mocked_device(modules=[Module.Light], alias="my_light", features=features)
    light = device.modules[Module.Light]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "brightness"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    light.set_brightness.assert_called_with(39, transition=None)
    light.set_brightness.reset_mock()


async def test_on_off_light(hass: HomeAssistant) -> None:
    """Test a light turns on and off."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light", features=[])
    light = device.modules[Module.Light]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()


async def test_off_at_start_light(hass: HomeAssistant) -> None:
    """Test a light off at startup."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light", features=[])
    light = device.modules[Module.Light]

    light.state = LightState(light_on=False)

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "off"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]


async def test_dimmer_turn_on_fix(hass: HomeAssistant) -> None:
    """Test a dimmer turns on without brightness being set."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(modules=[Module.Light], alias="my_light")
    light = device.modules[Module.Light]
    device.device_type = DeviceType.Dimmer
    light.state = LightState(light_on=False)

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
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
    features = [
        _mocked_feature("brightness", value=50),
        _mocked_feature("hsv", value=(10, 30, 5)),
        _mocked_feature(
            "color_temp", value=4000, minimum_value=4000, maximum_value=9000
        ),
    ]
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light", features=features
    )
    light = device.modules[Module.Light]
    light_effect = device.modules[Module.LightEffect]

    with (
        _patch_discovery(device=device),
        _patch_single_discovery(device=device),
        _patch_connect(device=device),
    ):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
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
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    light_effect.set_effect.assert_called_once_with(LightEffect.LIGHT_EFFECTS_OFF)
    light.set_color_temp.assert_called_once_with(4000, brightness=None, transition=None)
    light_effect.set_effect.reset_mock()
    light.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
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
        SERVICE_TURN_ON,
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
        SERVICE_TURN_ON,
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
        SERVICE_TURN_ON,
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RANDOM_EFFECT,
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
        SERVICE_RANDOM_EFFECT,
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
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_state.assert_called_once()
    light.set_state.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RANDOM_EFFECT,
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


@pytest.mark.parametrize(
    ("service_name", "service_params", "expected_extra_params"),
    [
        pytest.param(
            SERVICE_SEQUENCE_EFFECT,
            {
                "sequence": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
            },
            {
                "type": "sequence",
                "sequence": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
                "repeat_times": 0,
                "spread": 1,
                "direction": 4,
            },
            id="sequence",
        ),
        pytest.param(
            SERVICE_RANDOM_EFFECT,
            {"init_states": [340, 20, 50]},
            {"type": "random", "init_states": [[340, 20, 50]], "random_seed": 100},
            id="random",
        ),
    ],
)
async def test_smart_strip_effect_service_error(
    hass: HomeAssistant,
    service_name: str,
    service_params: dict,
    expected_extra_params: dict,
) -> None:
    """Test smart strip effect service errors."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light"
    )
    light_effect = device.modules[Module.LightEffect]

    with _patch_discovery(device=device), _patch_connect(device=device):
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    light_effect.set_custom_effect.side_effect = KasaException("failed")

    base = {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": 100,
        "name": "Custom",
        "segments": [0],
        "expansion_strategy": 1,
        "enable": 1,
        "duration": 0,
        "transition": 0,
    }
    expected_params = {**base, **expected_extra_params}
    expected_msg = f"Error trying to set custom effect {expected_params}: failed"

    with pytest.raises(HomeAssistantError, match=re.escape(expected_msg)):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                ATTR_ENTITY_ID: entity_id,
                **service_params,
            },
            blocking=True,
        )


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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    # fallback to set HSV when custom effect is not known so it does turn back on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEQUENCE_EFFECT,
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    assert not any(
        already_migrated_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    )

    with pytest.raises(HomeAssistantError, match=msg):
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
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
        await hass.config_entries.async_setup(already_migrated_config_entry.entry_id)
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
    features = [
        _mocked_feature("brightness", value=50),
        _mocked_feature("hsv", value=(10, 30, 5)),
        _mocked_feature(
            "color_temp", value=4000, minimum_value=4000, maximum_value=9000
        ),
    ]
    device = _mocked_device(
        modules=[Module.Light, Module.LightEffect], alias="my_light", features=features
    )
    light_effect = device.modules[Module.LightEffect]
    light_effect.effect = LightEffect.LIGHT_EFFECTS_OFF

    with _patch_discovery(device=device), _patch_connect(device=device):
        assert await hass.config_entries.async_setup(
            already_migrated_config_entry.entry_id
        )
        assert await async_setup_component(hass, SCENE_DOMAIN, {})
        await hass.async_block_till_done()

    entity_id = "light.my_light"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    freezer.tick(5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state is STATE_ON
    assert state.attributes["effect"] is EFFECT_OFF

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_CREATE,
        {CONF_SCENE_ID: "effect_off_scene", CONF_SNAPSHOT: [entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    scene_state = hass.states.get("scene.effect_off_scene")
    assert scene_state.state is STATE_UNKNOWN

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    freezer.tick(5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state is STATE_OFF

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "scene.effect_off_scene",
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
