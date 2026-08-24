"""Service-call tests for the Color helper."""

import math

import pytest
import voluptuous as vol

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_PARAMS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_SOURCE,
    ATTR_SOURCE_TYPE,
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
    # sRGB inputs echo exactly; only xy/hs are derived from them.
    assert state.state == "#FF0000"
    assert state.attributes[ATTR_HEX_COLOR] == "#FF0000"
    assert state.attributes[ATTR_RGB_COLOR] == [255, 0, 0]


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
    # Named colors resolve to their exact CSS3 sRGB triple.
    assert state.attributes[ATTR_RGB_COLOR] == [0, 0, 255]
    assert state.attributes[ATTR_HEX_COLOR] == "#0000FF"


@pytest.mark.parametrize(
    ("payload", "attr", "expected"),
    [
        pytest.param(
            {"hex_value": "#FF9E4D"}, ATTR_HEX_COLOR, "#FF9E4D", id="hex-exact"
        ),
        pytest.param(
            {"hex_value": "ff9e4d"}, ATTR_HEX_COLOR, "#FF9E4D", id="hex-normalized"
        ),
        pytest.param(
            {"rgb_color": [255, 158, 77]},
            ATTR_RGB_COLOR,
            [255, 158, 77],
            id="rgb-exact",
        ),
        pytest.param(
            {"hs_color": [200.5, 37.2]},
            ATTR_HS_COLOR,
            [200.5, 37.2],
            id="hs-exact-unrounded",
        ),
        pytest.param(
            {"xy_color": [0.44481, 0.40663]},
            ATTR_XY_COLOR,
            [0.44481, 0.40663],
            id="xy-exact-unrounded",
        ),
        pytest.param(
            {"color_temp_kelvin": 2700},
            ATTR_COLOR_TEMP_KELVIN,
            2700,
            id="kelvin-exact",
        ),
        pytest.param(
            {"color_name": "goldenrod"},
            ATTR_RGB_COLOR,
            [218, 165, 32],
            id="name-exact-table-rgb",
        ),
    ],
)
async def test_set_color_round_trips_exactly(
    hass: HomeAssistant, payload: dict, attr: str, expected: object
) -> None:
    """The attribute matching the input shape echoes the input exactly."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, **payload},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[attr] == expected


@pytest.mark.parametrize(
    ("payload", "expected_source"),
    [
        pytest.param(
            {"hex_value": "ff9e4d"}, {"hex_value": "#FF9E4D"}, id="hex-normalized"
        ),
        pytest.param(
            {"rgb_color": [255, 158, 77]},
            {"rgb_color": [255, 158, 77]},
            id="rgb",
        ),
        pytest.param({"hs_color": [200.5, 37.2]}, {"hs_color": [200.5, 37.2]}, id="hs"),
        pytest.param(
            {"xy_color": [0.44481, 0.40663]},
            {"xy_color": [0.44481, 0.40663]},
            id="xy",
        ),
        pytest.param(
            {"color_temp_kelvin": 2700}, {"color_temp_kelvin": 2700}, id="kelvin"
        ),
        pytest.param(
            {"color_name": "goldenrod"}, {"color_name": "goldenrod"}, id="name"
        ),
    ],
)
async def test_source_attribute_echoes_exact_input(
    hass: HomeAssistant, payload: dict, expected_source: dict
) -> None:
    """The source attribute names the shape the user set with its exact value.

    Its payload splats directly back into color.set_color, so setting it
    again must be accepted and leave the attribute unchanged.
    """
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, **payload},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SOURCE] == expected_source
    # source_type is the source dict's key, exposed for easy branching.
    assert state.attributes[ATTR_SOURCE_TYPE] == next(iter(expected_source))
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, **expected_source},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SOURCE] == expected_source


async def test_hex_input_is_the_state(hass: HomeAssistant) -> None:
    """A typed hex is the state string, byte for byte."""
    await _create_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: ENTITY_ID, "hex_value": "#FF9E4D"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == "#FF9E4D"
    assert state.attributes[ATTR_HEX_COLOR] == "#FF9E4D"
    # rgb is the exact triple of that hex; hs/xy are derived.
    assert state.attributes[ATTR_RGB_COLOR] == [255, 158, 77]


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
        pytest.param({"hs_color": [10**400, 50]}, id="hs-overflowing"),
        pytest.param({"xy_color": [10**400, 0.3]}, id="xy-overflowing"),
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
