"""Service-call tests for the Color helper."""

import math

import pytest
import voluptuous as vol

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_PARAMS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_MODE,
    DOMAIN,
    FIELD_BRIGHTNESS,
    KIND_WHITE,
    MODE_CHROMATIC,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

ENTITY_ID = "color.test_color"


async def _create_entry(hass: HomeAssistant) -> None:
    """Set up a chromatic entry producing the test entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Color",
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is not None


async def test_set_color_via_hex(hass: HomeAssistant) -> None:
    """Test setting a color from a hex value."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#FF0000"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    # Hex round-trips through xy with some gamut loss; the red component
    # should still dominate.
    r, g, b = state.attributes[ATTR_RGB_COLOR]
    assert r > 200
    assert g < 50
    assert b < 50


async def test_set_color_via_kelvin_marks_white(hass: HomeAssistant) -> None:
    """Test setting a color temperature marks the color as white."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "color_temp_kelvin": 3000},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3000


async def test_set_color_via_color_name(hass: HomeAssistant) -> None:
    """Test setting a color from a CSS3 color name."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "color_name": "blue"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    _r, _g, b = state.attributes[ATTR_RGB_COLOR]
    assert b > 200


async def test_set_brightness_then_clear(hass: HomeAssistant) -> None:
    """Test setting and clearing the stored brightness."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID, FIELD_BRIGHTNESS: 180},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] == 180

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_BRIGHTNESS] is None


async def test_set_color_rejects_multiple_shapes(hass: HomeAssistant) -> None:
    """Test the schema rejects two color shapes in one call."""
    await _create_entry(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "hex_value": "#FF0000",
                "rgb_color": [0, 255, 0],
            },
            blocking=True,
        )


async def test_set_color_rejects_missing_shape(hass: HomeAssistant) -> None:
    """Test the schema rejects a call without any color shape."""
    await _create_entry(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {ATTR_ENTITY_ID: ENTITY_ID, FIELD_BRIGHTNESS: 100},
            blocking=True,
        )


@pytest.mark.parametrize(
    "invalid_data",
    [
        pytest.param({"hex_value": "#NOTHEX"}, id="invalid-hex"),
        pytest.param({"color_name": "definitely-not-a-color"}, id="unknown-name"),
    ],
)
async def test_set_color_invalid_value_raises_service_validation_error(
    hass: HomeAssistant, invalid_data: dict[str, str]
) -> None:
    """Test invalid color values raise ServiceValidationError."""
    await _create_entry(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {ATTR_ENTITY_ID: ENTITY_ID, **invalid_data},
            blocking=True,
        )


async def test_color_params_chromatic(hass: HomeAssistant) -> None:
    """Chromatic value exposes xy_color only; brightness appears when stored."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#FF0000"},
        blocking=True,
    )
    params = hass.states.get(ENTITY_ID).attributes[ATTR_COLOR_PARAMS]
    assert set(params) == {"xy_color"}
    x, y = params["xy_color"]
    rounded = hass.states.get(ENTITY_ID).attributes[ATTR_XY_COLOR]
    assert [round(x, 4), round(y, 4)] == rounded

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID, FIELD_BRIGHTNESS: 128},
        blocking=True,
    )
    params = hass.states.get(ENTITY_ID).attributes[ATTR_COLOR_PARAMS]
    assert set(params) == {"xy_color", "brightness"}
    assert params["brightness"] == 128

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_BRIGHTNESS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    params = hass.states.get(ENTITY_ID).attributes[ATTR_COLOR_PARAMS]
    assert "brightness" not in params


async def test_color_params_white(hass: HomeAssistant) -> None:
    """White value exposes color_temp_kelvin, never xy_color."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "color_temp_kelvin": 3000, FIELD_BRIGHTNESS: 200},
        blocking=True,
    )
    params = hass.states.get(ENTITY_ID).attributes[ATTR_COLOR_PARAMS]
    assert params == {"color_temp_kelvin": 3000, "brightness": 200}


@pytest.mark.parametrize(
    "payload",
    [
        {"hex_value": "#000000"},
        {"rgb_color": [0, 0, 0]},
        {"color_name": "black"},
    ],
)
async def test_set_color_rejects_pure_black(hass: HomeAssistant, payload: dict) -> None:
    """Zero-intensity inputs have no chromaticity and must be rejected."""
    await _create_entry(hass)
    before = hass.states.get(ENTITY_ID).state
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {ATTR_ENTITY_ID: ENTITY_ID, **payload},
            blocking=True,
        )
    assert hass.states.get(ENTITY_ID).state == before


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"color_temp_kelvin": math.inf}, id="kelvin-infinite"),
        pytest.param({"brightness": math.inf}, id="brightness-infinite"),
        pytest.param({"rgb_color": [math.inf, 0, 0]}, id="rgb-infinite"),
    ],
)
async def test_set_color_rejects_infinite_numbers(
    hass: HomeAssistant, payload: dict
) -> None:
    """Infinite numbers fail schema validation instead of raising OverflowError."""
    await _create_entry(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {ATTR_ENTITY_ID: ENTITY_ID, **payload},
            blocking=True,
        )


async def test_set_brightness_rejects_infinite(hass: HomeAssistant) -> None:
    """Infinite brightness fails schema validation for set_brightness."""
    await _create_entry(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_BRIGHTNESS,
            {ATTR_ENTITY_ID: ENTITY_ID, "brightness": math.inf},
            blocking=True,
        )
