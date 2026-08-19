"""Unit tests for the color normalizer.

These are pure-Python tests (no HA event loop) so they're cheap to run and
catch the bulk of normalization regressions before any integration tests.
"""

import math

import pytest

from homeassistant.components.color.color_math import (
    ColorInputError,
    derive_hex,
    derive_hs,
    derive_kelvin,
    derive_rgb,
    normalize,
)
from homeassistant.components.color.const import (
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
    KIND_CHROMATIC,
    KIND_WHITE,
)


def test_normalize_requires_exactly_one_shape() -> None:
    """Test that normalize rejects empty and ambiguous inputs."""
    with pytest.raises(ColorInputError):
        normalize({})
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "#FF0000", FIELD_RGB: [0, 255, 0]})


@pytest.mark.parametrize(
    ("hex_in", "expected_rgb"),
    [
        pytest.param("#FF0000", (255, 0, 0), id="red"),
        pytest.param("ff0000", (255, 0, 0), id="red-no-hash"),
        pytest.param("#00ff00", (0, 255, 0), id="green"),
        pytest.param("#0000FF", (0, 0, 255), id="blue"),
    ],
)
def test_normalize_hex_round_trips_exactly(
    hex_in: str, expected_rgb: tuple[int, int, int]
) -> None:
    """Hex inputs derive back to the exact RGB, bypassing the lossy xy path."""
    canonical = normalize({FIELD_HEX: hex_in})
    assert canonical.kind == KIND_CHROMATIC
    assert derive_rgb(canonical) == expected_rgb


def test_normalize_invalid_hex() -> None:
    """Test invalid hex strings are rejected."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "#GGGGGG"})
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "#FFF"})
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "##FF0000"})


def test_normalize_rgb_validates_range() -> None:
    """Test RGB triplets are validated."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_RGB: [256, 0, 0]})
    with pytest.raises(ColorInputError):
        normalize({FIELD_RGB: [0, 0]})
    canonical = normalize({FIELD_RGB: [128, 64, 32]})
    assert canonical.kind == KIND_CHROMATIC


def test_normalize_hs_validates_range() -> None:
    """Test hue/saturation pairs are validated."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_HS: [400, 50]})
    with pytest.raises(ColorInputError):
        normalize({FIELD_HS: [180, 150]})
    canonical = normalize({FIELD_HS: [180, 50]})
    assert canonical.kind == KIND_CHROMATIC


def test_normalize_xy_passthrough() -> None:
    """Test xy inputs are stored as-is."""
    canonical = normalize({FIELD_XY: [0.4, 0.4]})
    assert canonical.kind == KIND_CHROMATIC
    assert canonical.xy == (0.4, 0.4)


def test_normalize_kelvin_sets_kind_white() -> None:
    """Test kelvin inputs produce a white canonical color."""
    canonical = normalize({FIELD_KELVIN: 4000})
    assert canonical.kind == KIND_WHITE
    assert canonical.kelvin == 4000
    # The xy on the Planckian locus should be in the warm-white quadrant.
    x, y = canonical.xy
    assert 0.25 < x < 0.45
    assert 0.25 < y < 0.45


def test_normalize_kelvin_out_of_range() -> None:
    """Test kelvin range validation."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_KELVIN: 500})
    with pytest.raises(ColorInputError):
        normalize({FIELD_KELVIN: 100_000})


def test_normalize_color_name() -> None:
    """Test CSS3 color names normalize."""
    canonical = normalize({FIELD_COLOR_NAME: "red"})
    assert canonical.kind == KIND_CHROMATIC
    r, _g, _b = derive_rgb(canonical)
    assert r > 200


def test_normalize_unknown_color_name() -> None:
    """Test unknown color names are rejected."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_COLOR_NAME: "definitely-not-a-color"})


def test_derive_hex_format() -> None:
    """Test the derived hex string format."""
    canonical = normalize({FIELD_HEX: "#FF8000"})
    hex_out = derive_hex(canonical)
    assert hex_out.startswith("#")
    assert len(hex_out) == 7
    assert hex_out == hex_out.upper()


def test_derive_kelvin_for_white_returns_stored_value() -> None:
    """Test stored kelvin round-trips for whites."""
    canonical = normalize({FIELD_KELVIN: 3500})
    assert derive_kelvin(canonical) == 3500


def test_derive_kelvin_for_chromatic_returns_none() -> None:
    """Chromatic colors must not emit a McCamy-guessed kelvin."""
    canonical = normalize({FIELD_HEX: "#FF0000"})
    assert derive_kelvin(canonical) is None


def test_derive_hs_in_expected_ranges() -> None:
    """Test derived hue/saturation stay in range."""
    canonical = normalize({FIELD_HEX: "#FF0000"})
    hue, sat = derive_hs(canonical)
    assert 0 <= hue <= 360
    assert 0 <= sat <= 100


@pytest.mark.parametrize(
    "inputs",
    [
        pytest.param({FIELD_HS: "not-a-pair"}, id="hs-not-a-sequence"),
        pytest.param({FIELD_HS: [180]}, id="hs-wrong-length"),
        pytest.param({FIELD_XY: [0.4]}, id="xy-wrong-length"),
        pytest.param({FIELD_XY: [1.5, 0.4]}, id="xy-out-of-range"),
        pytest.param({FIELD_XY: [0.0, 0.0]}, id="xy-zero-luminance"),
        pytest.param({FIELD_XY: [0.7, 0.7]}, id="xy-outside-triangle"),
        pytest.param({FIELD_KELVIN: "warmish"}, id="kelvin-not-an-int"),
        pytest.param({FIELD_KELVIN: None}, id="kelvin-none-explicit"),
        pytest.param({FIELD_KELVIN: math.inf}, id="kelvin-infinite"),
        pytest.param({FIELD_RGB: ["abc", 0, 0]}, id="rgb-non-numeric"),
        pytest.param({FIELD_RGB: [math.inf, 0, 0]}, id="rgb-infinite"),
        pytest.param({FIELD_HS: ["x", 1]}, id="hs-non-numeric"),
        pytest.param({FIELD_HS: [10**400, 50]}, id="hs-overflowing"),
        pytest.param({FIELD_XY: ["x", 0.3]}, id="xy-non-numeric"),
        pytest.param({FIELD_XY: [10**400, 0.3]}, id="xy-overflowing"),
    ],
)
def test_normalize_rejects_malformed_shapes(inputs: dict) -> None:
    """Test malformed input shapes raise ColorInputError."""
    with pytest.raises(ColorInputError):
        normalize(inputs)


@pytest.mark.parametrize(
    ("inputs", "field", "value"),
    [
        pytest.param(
            {FIELD_HEX: "#ff9e4d"}, FIELD_HEX, "#FF9E4D", id="hex-normalized-upper"
        ),
        pytest.param(
            {FIELD_RGB: [255, 158, 77]}, FIELD_RGB, (255, 158, 77), id="rgb-exact"
        ),
        pytest.param({FIELD_HS: [200.5, 37.2]}, FIELD_HS, (200.5, 37.2), id="hs-exact"),
        pytest.param(
            {FIELD_XY: [0.44481, 0.40663]},
            FIELD_XY,
            (0.44481, 0.40663),
            id="xy-exact",
        ),
        pytest.param({FIELD_KELVIN: 2700}, FIELD_KELVIN, 2700, id="kelvin-exact"),
        pytest.param(
            {FIELD_COLOR_NAME: "goldenrod"},
            FIELD_COLOR_NAME,
            "goldenrod",
            id="name-kept",
        ),
    ],
)
def test_normalize_records_exact_source(
    inputs: dict, field: str, value: object
) -> None:
    """The canonical color keeps the validated input for exact echoes."""
    canonical = normalize(inputs)
    assert canonical.source_field == field
    assert canonical.source_value == value


def test_derive_hex_echoes_hex_source() -> None:
    """A hex source derives back byte for byte (uppercased)."""
    assert derive_hex(normalize({FIELD_HEX: "#ff9e4d"})) == "#FF9E4D"


def test_derive_rgb_echoes_rgb_source() -> None:
    """An rgb source derives back as the exact triple."""
    assert derive_rgb(normalize({FIELD_RGB: [255, 158, 77]})) == (255, 158, 77)


def test_derive_hs_echoes_hs_source_unrounded() -> None:
    """An hs source derives back as the exact floats, unrounded."""
    assert derive_hs(normalize({FIELD_HS: [200.51, 37.29]})) == (200.51, 37.29)


def test_derive_rgb_for_name_uses_color_table() -> None:
    """A color name derives the exact CSS3 table triple, not a gamut round-trip."""
    assert derive_rgb(normalize({FIELD_COLOR_NAME: "goldenrod"})) == (218, 165, 32)
