"""Test the Kuler Sky lights."""
from unittest.mock import MagicMock, patch

import pykulersky
import pytest
from pytest import approx

from homeassistant.components.kulersky.const import (
    DATA_ADDRESSES,
    DATA_DISCOVERY_SUBSCRIPTION,
    DOMAIN,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    SCAN_INTERVAL,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
async def mock_entry(hass):
    """Create a mock light entity."""
    return MockConfigEntry(domain=DOMAIN)


@pytest.fixture
async def mock_light(hass, mock_entry):
    """Create a mock light entity."""

    light = MagicMock(spec=pykulersky.Light)
    light.address = "AA:BB:CC:11:22:33"
    light.name = "Bedroom"
    light.connect.return_value = True
    light.get_color.return_value = (0, 0, 0, 0)
    with patch(
        "homeassistant.components.kulersky.light.pykulersky.discover",
        return_value=[light],
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert light.connect.called

        yield light


async def test_init(hass, mock_light):
    """Test platform setup."""
    state = hass.states.get("light.bedroom")
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
    }

    with patch.object(hass.loop, "stop"):
        await hass.async_stop()
        await hass.async_block_till_done()

    assert mock_light.disconnect.called


async def test_remove_entry(hass, mock_light, mock_entry):
    """Test platform setup."""
    assert hass.data[DOMAIN][DATA_ADDRESSES] == {"AA:BB:CC:11:22:33"}
    assert DATA_DISCOVERY_SUBSCRIPTION in hass.data[DOMAIN]

    await hass.config_entries.async_remove(mock_entry.entry_id)

    assert mock_light.disconnect.called
    assert DOMAIN not in hass.data


async def test_remove_entry_exceptions_caught(hass, mock_light, mock_entry):
    """Assert that disconnect exceptions are caught."""
    mock_light.disconnect.side_effect = pykulersky.PykulerskyException("Mock error")
    await hass.config_entries.async_remove(mock_entry.entry_id)

    assert mock_light.disconnect.called


async def test_update_exception(hass, mock_light):
    """Test platform setup."""

    mock_light.get_color.side_effect = pykulersky.PykulerskyException
    await async_update_entity(hass, "light.bedroom")
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_light_turn_on(hass, mock_light):
    """Test KulerSkyLight turn_on."""
    mock_light.get_color.return_value = (255, 255, 255, 255)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(255, 255, 255, 255)

    mock_light.get_color.return_value = (50, 50, 50, 50)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(50, 50, 50, 50)

    mock_light.get_color.return_value = (50, 25, 13, 6)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_RGBW_COLOR: (255, 128, 64, 32)},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(50, 25, 13, 6)

    # RGB color is converted to RGBW by assigning the white component to the white
    # channel, see color_rgb_to_rgbw
    mock_light.get_color.return_value = (0, 17, 50, 17)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_RGB_COLOR: (64, 128, 255)},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(0, 17, 50, 17)

    # HS color is converted to RGBW by assigning the white component to the white
    # channel, see color_rgb_to_rgbw
    mock_light.get_color.return_value = (50, 41, 0, 50)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_HS_COLOR: (50, 50)},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(50, 41, 0, 50)


async def test_light_turn_off(hass, mock_light):
    """Test KulerSkyLight turn_on."""
    mock_light.get_color.return_value = (0, 0, 0, 0)
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_light.set_color.assert_called_with(0, 0, 0, 0)


async def test_light_update(hass, mock_light):
    """Test KulerSkyLight update."""
    utcnow = dt_util.utcnow()

    state = hass.states.get("light.bedroom")
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
    }

    # Test an exception during discovery
    mock_light.get_color.side_effect = pykulersky.PykulerskyException("TEST")
    utcnow = utcnow + SCAN_INTERVAL
    async_fire_time_changed(hass, utcnow)
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom")
    assert state.state == STATE_UNAVAILABLE
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
    }

    mock_light.get_color.side_effect = None
    mock_light.get_color.return_value = (80, 160, 255, 0)
    utcnow = utcnow + SCAN_INTERVAL
    async_fire_time_changed(hass, utcnow)
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom")
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: ColorMode.RGBW,
        ATTR_BRIGHTNESS: 255,
        ATTR_HS_COLOR: (approx(212.571), approx(68.627)),
        ATTR_RGB_COLOR: (80, 160, 255),
        ATTR_RGBW_COLOR: (80, 160, 255, 0),
        ATTR_XY_COLOR: (approx(0.17), approx(0.193)),
    }

    mock_light.get_color.side_effect = None
    mock_light.get_color.return_value = (80, 160, 200, 255)
    utcnow = utcnow + SCAN_INTERVAL
    async_fire_time_changed(hass, utcnow)
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom")
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: ColorMode.RGBW,
        ATTR_BRIGHTNESS: 255,
        ATTR_HS_COLOR: (approx(199.701), approx(26.275)),
        ATTR_RGB_COLOR: (188, 233, 255),
        ATTR_RGBW_COLOR: (80, 160, 200, 255),
        ATTR_XY_COLOR: (approx(0.259), approx(0.306)),
    }

    mock_light.get_color.side_effect = None
    mock_light.get_color.return_value = (80, 160, 200, 240)
    utcnow = utcnow + SCAN_INTERVAL
    async_fire_time_changed(hass, utcnow)
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom")
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        ATTR_FRIENDLY_NAME: "Bedroom",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: ColorMode.RGBW,
        ATTR_BRIGHTNESS: 240,
        ATTR_HS_COLOR: (approx(200.0), approx(27.059)),
        ATTR_RGB_COLOR: (186, 232, 255),
        ATTR_RGBW_COLOR: (85, 170, 212, 255),
        ATTR_XY_COLOR: (approx(0.257), approx(0.305)),
    }
