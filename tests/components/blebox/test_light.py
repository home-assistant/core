"""BleBox light entities tests."""

import logging

import blebox_uniapi
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.util import color

from .conftest import async_setup_entity, mock_feature

from tests.async_mock import AsyncMock, PropertyMock

ALL_LIGHT_FIXTURES = ["dimmer", "wlightbox_s", "wlightbox"]


@pytest.fixture(name="dimmer")
def dimmer_fixture():
    """Return a default light entity mock."""

    feature = mock_feature(
        "lights",
        blebox_uniapi.light.Light,
        unique_id="BleBox-dimmerBox-1afe34e750b8-brightness",
        full_name="dimmerBox-brightness",
        device_class=None,
        brightness=65,
        is_on=True,
        supports_color=False,
        supports_white=False,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My dimmer")
    type(product).model = PropertyMock(return_value="dimmerBox")
    return (feature, "light.dimmerbox_brightness")


async def test_dimmer_init(dimmer, hass, config):
    """Test cover default state."""

    _, entity_id = dimmer
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-dimmerBox-1afe34e750b8-brightness"

    state = hass.states.get(entity_id)
    assert state.name == "dimmerBox-brightness"

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_BRIGHTNESS

    assert state.attributes[ATTR_BRIGHTNESS] == 65
    assert state.state == STATE_ON

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My dimmer"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "dimmerBox"
    assert device.sw_version == "1.23"


async def test_dimmer_update(dimmer, hass, config):
    """Test light updating."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.brightness = 53

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_BRIGHTNESS] == 53
    assert state.state == STATE_ON


async def test_dimmer_on(dimmer, hass, config):
    """Test light on."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(brightness):
        assert brightness == 254
        feature_mock.brightness = 254  # on
        feature_mock.is_on = True  # on

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 254


async def test_dimmer_on_with_brightness(dimmer, hass, config):
    """Test light on with a brightness value."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(brightness):
        assert brightness == 202
        feature_mock.brightness = 202  # on
        feature_mock.is_on = True  # on

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    def apply(value, brightness):
        assert value == 254
        return brightness

    feature_mock.apply_brightness = apply
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_BRIGHTNESS: 202},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_BRIGHTNESS] == 202
    assert state.state == STATE_ON


async def test_dimmer_off(dimmer, hass, config):
    """Test light off."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    def turn_off():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off

    feature_mock.async_off = AsyncMock(side_effect=turn_off)
    await hass.services.async_call(
        "light", SERVICE_TURN_OFF, {"entity_id": entity_id}, blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert ATTR_BRIGHTNESS not in state.attributes


@pytest.fixture(name="wlightbox_s")
def wlightboxs_fixture():
    """Return a default light entity mock."""

    feature = mock_feature(
        "lights",
        blebox_uniapi.light.Light,
        unique_id="BleBox-wLightBoxS-1afe34e750b8-color",
        full_name="wLightBoxS-color",
        device_class=None,
        brightness=None,
        is_on=None,
        supports_color=False,
        supports_white=False,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My wLightBoxS")
    type(product).model = PropertyMock(return_value="wLightBoxS")
    return (feature, "light.wlightboxs_color")


async def test_wlightbox_s_init(wlightbox_s, hass, config):
    """Test cover default state."""

    _, entity_id = wlightbox_s
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-wLightBoxS-1afe34e750b8-color"

    state = hass.states.get(entity_id)
    assert state.name == "wLightBoxS-color"

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_BRIGHTNESS

    assert ATTR_BRIGHTNESS not in state.attributes
    assert state.state == STATE_OFF

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My wLightBoxS"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "wLightBoxS"
    assert device.sw_version == "1.23"


async def test_wlightbox_s_update(wlightbox_s, hass, config):
    """Test light updating."""

    feature_mock, entity_id = wlightbox_s

    def initial_update():
        feature_mock.brightness = 0xAB
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 0xAB


async def test_wlightbox_s_on(wlightbox_s, hass, config):
    """Test light on."""

    feature_mock, entity_id = wlightbox_s

    def initial_update():
        feature_mock.is_on = False
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(brightness):
        assert brightness == 254
        feature_mock.brightness = 254  # on
        feature_mock.is_on = True  # on

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_BRIGHTNESS] == 254
    assert state.state == STATE_ON


@pytest.fixture(name="wlightbox")
def wlightbox_fixture():
    """Return a default light entity mock."""

    feature = mock_feature(
        "lights",
        blebox_uniapi.light.Light,
        unique_id="BleBox-wLightBox-1afe34e750b8-color",
        full_name="wLightBox-color",
        device_class=None,
        is_on=None,
        supports_color=True,
        supports_white=True,
        white_value=None,
        rgbw_hex=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My wLightBox")
    type(product).model = PropertyMock(return_value="wLightBox")
    return (feature, "light.wlightbox_color")


async def test_wlightbox_init(wlightbox, hass, config):
    """Test cover default state."""

    _, entity_id = wlightbox
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-wLightBox-1afe34e750b8-color"

    state = hass.states.get(entity_id)
    assert state.name == "wLightBox-color"

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_WHITE_VALUE
    assert supported_features & SUPPORT_COLOR

    assert ATTR_WHITE_VALUE not in state.attributes
    assert ATTR_HS_COLOR not in state.attributes
    assert ATTR_BRIGHTNESS not in state.attributes
    assert state.state == STATE_OFF

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My wLightBox"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "wLightBox"
    assert device.sw_version == "1.23"


async def test_wlightbox_update(wlightbox, hass, config):
    """Test light updating."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = True
        feature_mock.rgbw_hex = "fa00203A"
        feature_mock.white_value = 0x3A

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HS_COLOR] == (352.32, 100.0)
    assert state.attributes[ATTR_WHITE_VALUE] == 0x3A
    assert state.state == STATE_ON


async def test_wlightbox_on_via_just_whiteness(wlightbox, hass, config):
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(value):
        feature_mock.is_on = True
        assert value == "f1e2d3c7"
        feature_mock.white_value = 0xC7  # on
        feature_mock.rgbw_hex = "f1e2d3c7"

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    def apply_white(value, white):
        assert value == "f1e2d305"
        assert white == 0xC7
        return "f1e2d3c7"

    feature_mock.apply_white = apply_white

    feature_mock.sensible_on_value = "f1e2d305"

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_WHITE_VALUE: 0xC7},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_WHITE_VALUE] == 0xC7

    assert state.attributes[ATTR_HS_COLOR] == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)


async def test_wlightbox_on_via_reset_whiteness(wlightbox, hass, config):
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(value):
        feature_mock.is_on = True
        feature_mock.white_value = 0x0
        assert value == "f1e2d300"
        feature_mock.rgbw_hex = "f1e2d300"

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    def apply_white(value, white):
        assert value == "f1e2d305"
        assert white == 0x0
        return "f1e2d300"

    feature_mock.apply_white = apply_white

    feature_mock.sensible_on_value = "f1e2d305"

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_WHITE_VALUE: 0x0},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_WHITE_VALUE] == 0x0
    assert state.attributes[ATTR_HS_COLOR] == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)


async def test_wlightbox_on_via_just_hsl_color(wlightbox, hass, config):
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False
        feature_mock.rgbw_hex = "00000000"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    hs_color = color.color_RGB_to_hs(0xFF, 0xA1, 0xB2)

    def turn_on(value):
        feature_mock.is_on = True
        assert value == "ffa1b2e4"
        feature_mock.white_value = 0xE4
        feature_mock.rgbw_hex = value

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    def apply_color(value, color_value):
        assert value == "c1a2e3e4"
        assert color_value == "ffa0b1"
        return "ffa1b2e4"

    feature_mock.apply_color = apply_color
    feature_mock.sensible_on_value = "c1a2e3e4"

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_HS_COLOR: hs_color},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HS_COLOR] == hs_color
    assert state.attributes[ATTR_WHITE_VALUE] == 0xE4
    assert state.state == STATE_ON


async def test_wlightbox_on_to_last_color(wlightbox, hass, config):
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(value):
        feature_mock.is_on = True
        assert value == "f1e2d3e4"
        feature_mock.white_value = 0xE4
        feature_mock.rgbw_hex = value

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    feature_mock.sensible_on_value = "f1e2d3e4"

    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_WHITE_VALUE] == 0xE4
    assert state.attributes[ATTR_HS_COLOR] == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)
    assert state.state == STATE_ON


async def test_wlightbox_off(wlightbox, hass, config):
    """Test light off."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    def turn_off():
        feature_mock.is_on = False
        feature_mock.white_value = 0x0
        feature_mock.rgbw_hex = "00000000"

    feature_mock.async_off = AsyncMock(side_effect=turn_off)

    await hass.services.async_call(
        "light", SERVICE_TURN_OFF, {"entity_id": entity_id}, blocking=True,
    )

    state = hass.states.get(entity_id)
    assert ATTR_WHITE_VALUE not in state.attributes
    assert ATTR_HS_COLOR not in state.attributes
    assert state.state == STATE_OFF


@pytest.mark.parametrize("feature", ALL_LIGHT_FIXTURES, indirect=["feature"])
async def test_update_failure(feature, hass, config, caplog):
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = feature
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, config, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text


@pytest.mark.parametrize("feature", ALL_LIGHT_FIXTURES, indirect=["feature"])
async def test_turn_on_failure(feature, hass, config, caplog):
    """Test that turn_on failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = feature
    feature_mock.async_on = AsyncMock(side_effect=blebox_uniapi.error.BadOnValueError)
    await async_setup_entity(hass, config, entity_id)

    feature_mock.sensible_on_value = 123
    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {"entity_id": entity_id}, blocking=True,
    )

    assert (
        f"Turning on '{feature_mock.full_name}' failed: Bad value 123 ()" in caplog.text
    )
