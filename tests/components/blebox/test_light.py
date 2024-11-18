"""BleBox light entities tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import async_setup_entity, mock_feature

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
        color_mode=blebox_uniapi.light.BleboxColorMode.MONO,
        effect_list=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My dimmer")
    type(product).model = PropertyMock(return_value="dimmerBox")
    return (feature, "light.dimmerbox_brightness")


async def test_dimmer_init(
    dimmer, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test cover default state."""

    _, entity_id = dimmer
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-dimmerBox-1afe34e750b8-brightness"

    state = hass.states.get(entity_id)
    assert state.name == "dimmerBox-brightness"

    color_modes = state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert color_modes == [ColorMode.BRIGHTNESS]

    assert state.attributes[ATTR_BRIGHTNESS] == 65
    assert state.state == STATE_ON

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My dimmer"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "dimmerBox"
    assert device.sw_version == "1.23"


async def test_dimmer_update(dimmer, hass: HomeAssistant) -> None:
    """Test light updating."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.brightness = 53

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_BRIGHTNESS] == 53
    assert state.state == STATE_ON


async def test_dimmer_on(dimmer, hass: HomeAssistant) -> None:
    """Test light on."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(brightness):
        assert brightness == 254
        feature_mock.brightness = 254  # on
        feature_mock.is_on = True  # on

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 254


async def test_dimmer_on_with_brightness(dimmer, hass: HomeAssistant) -> None:
    """Test light on with a brightness value."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
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


async def test_dimmer_off(dimmer, hass: HomeAssistant) -> None:
    """Test light off."""

    feature_mock, entity_id = dimmer

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    def turn_off():
        feature_mock.is_on = False
        feature_mock.brightness = 0  # off

    feature_mock.async_off = AsyncMock(side_effect=turn_off)
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None


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
        color_mode=blebox_uniapi.light.BleboxColorMode.MONO,
        effect_list=["NONE", "PL", "RELAX"],
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My wLightBoxS")
    type(product).model = PropertyMock(return_value="wLightBoxS")
    return (feature, "light.wlightboxs_color")


async def test_wlightbox_s_init(
    wlightbox_s, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test cover default state."""

    _, entity_id = wlightbox_s
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-wLightBoxS-1afe34e750b8-color"

    state = hass.states.get(entity_id)
    assert state.name == "wLightBoxS-color"

    color_modes = state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert color_modes == [ColorMode.BRIGHTNESS]

    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My wLightBoxS"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "wLightBoxS"
    assert device.sw_version == "1.23"


async def test_wlightbox_s_update(wlightbox_s, hass: HomeAssistant) -> None:
    """Test light updating."""

    feature_mock, entity_id = wlightbox_s

    def initial_update():
        feature_mock.brightness = 0xAB
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 0xAB


async def test_wlightbox_s_on(wlightbox_s, hass: HomeAssistant) -> None:
    """Test light on."""

    feature_mock, entity_id = wlightbox_s

    def initial_update():
        feature_mock.is_on = False
        feature_mock.sensible_on_value = 254

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(brightness):
        assert brightness == 254
        feature_mock.brightness = 254  # on
        feature_mock.is_on = True  # on

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
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
        color_mode=blebox_uniapi.light.BleboxColorMode.RGBW,
        effect="NONE",
        effect_list=["NONE", "PL", "POLICE"],
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My wLightBox")
    type(product).model = PropertyMock(return_value="wLightBox")
    return (feature, "light.wlightbox_color")


async def test_wlightbox_init(
    wlightbox, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test cover default state."""

    _, entity_id = wlightbox
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-wLightBox-1afe34e750b8-color"

    state = hass.states.get(entity_id)
    assert state.name == "wLightBox-color"

    color_modes = state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert color_modes == [ColorMode.RGBW]

    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.attributes[ATTR_RGBW_COLOR] is None
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My wLightBox"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "wLightBox"
    assert device.sw_version == "1.23"


async def test_wlightbox_update(wlightbox, hass: HomeAssistant) -> None:
    """Test light updating."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = True
        feature_mock.rgbw_hex = "fa00203A"
        feature_mock.white_value = 0x3A

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_RGBW_COLOR] == (0xFA, 0x00, 0x20, 0x3A)
    assert state.state == STATE_ON


async def test_wlightbox_on_rgbw(wlightbox, hass: HomeAssistant) -> None:
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(value):
        feature_mock.is_on = True
        assert value == [193, 210, 243, 199]
        feature_mock.white_value = 0xC7  # on
        feature_mock.rgbw_hex = "c1d2f3c7"

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    def apply_white(value, white):
        assert value == "00010203"
        assert white == 0xC7
        return "000102c7"

    feature_mock.apply_white = apply_white

    def apply_color(value, color_value):
        assert value == "000102c7"
        assert color_value == "c1d2f3"
        return "c1d2f3c7"

    feature_mock.apply_color = apply_color
    feature_mock.sensible_on_value = "00010203"

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_RGBW_COLOR: (0xC1, 0xD2, 0xF3, 0xC7)},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGBW_COLOR] == (0xC1, 0xD2, 0xF3, 0xC7)


async def test_wlightbox_on_to_last_color(wlightbox, hass: HomeAssistant) -> None:
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
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
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_RGBW_COLOR] == (0xF1, 0xE2, 0xD3, 0xE4)
    assert state.state == STATE_ON


async def test_wlightbox_off(wlightbox, hass: HomeAssistant) -> None:
    """Test light off."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    def turn_off():
        feature_mock.is_on = False
        feature_mock.white_value = 0x0
        feature_mock.rgbw_hex = "00000000"

    feature_mock.async_off = AsyncMock(side_effect=turn_off)

    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_RGBW_COLOR] is None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("feature", ALL_LIGHT_FIXTURES, indirect=["feature"])
async def test_update_failure(
    feature, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = feature
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text


@pytest.mark.parametrize("feature", ALL_LIGHT_FIXTURES, indirect=["feature"])
async def test_turn_on_failure(
    feature, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that turn_on failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = feature
    feature_mock.async_on = AsyncMock(side_effect=ValueError)
    await async_setup_entity(hass, entity_id)

    feature_mock.sensible_on_value = 123
    with pytest.raises(ValueError) as info:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {"entity_id": entity_id},
            blocking=True,
        )

    assert f"Turning on '{feature_mock.full_name}' failed: Bad value 123" in str(
        info.value
    )


async def test_wlightbox_on_effect(wlightbox, hass: HomeAssistant) -> None:
    """Test light on."""

    feature_mock, entity_id = wlightbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
    feature_mock.async_update = AsyncMock()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    def turn_on(value):
        feature_mock.is_on = True
        feature_mock.effect = "POLICE"

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    with pytest.raises(ValueError) as info:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {"entity_id": entity_id, ATTR_EFFECT: "NOT IN LIST"},
            blocking=True,
        )

    assert (
        f"Turning on with effect '{feature_mock.full_name}' failed: "
        "NOT IN LIST not in effect list."
    ) in str(info.value)

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_EFFECT: "POLICE"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_EFFECT] == "POLICE"
