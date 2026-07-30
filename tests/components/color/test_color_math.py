"""Unit tests for the color normalizer.

These are pure-Python tests (no HA event loop) so they're cheap to run and
catch the bulk of normalization regressions before any integration tests.
"""

import pytest

from homeassistant.components.color.color_math import (
    ColorInputError,
    compute_source_hex,
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
        ("#FF0000", (255, 0, 0)),
        ("ff0000", (255, 0, 0)),
        ("#00ff00", (0, 255, 0)),
        ("#0000FF", (0, 0, 255)),
    ],
)
def test_normalize_hex_round_trips_via_xy(
    hex_in: str, expected_rgb: tuple[int, int, int]
) -> None:
    """Test hex inputs normalize and derive back to a similar RGB."""
    canonical = normalize({FIELD_HEX: hex_in})
    assert canonical.kind == KIND_CHROMATIC
    # xy is chromaticity only; the round-trip introduces a small per-channel
    # drift (more pronounced at the gamut edges). The dominant channel should
    # clearly win; non-dominant channels should stay near zero.
    dominant = expected_rgb.index(max(expected_rgb))
    for i, got in enumerate(derive_rgb(canonical)):
        if i == dominant:
            assert got > 200, f"dominant channel too low: {got}"
        else:
            assert got < 30, f"off-channel too high: {got}"


def test_normalize_invalid_hex() -> None:
    """Test invalid hex strings are rejected."""
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "#GGGGGG"})
    with pytest.raises(ColorInputError):
        normalize({FIELD_HEX: "#FFF"})


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
        pytest.param({FIELD_KELVIN: "warmish"}, id="kelvin-not-an-int"),
        pytest.param({FIELD_KELVIN: None}, id="kelvin-none-explicit"),
    ],
)
def test_normalize_rejects_malformed_shapes(inputs: dict) -> None:
    """Test malformed input shapes raise ColorInputError."""
    with pytest.raises(ColorInputError):
        normalize(inputs)


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        pytest.param({FIELD_HEX: "#FF8000"}, "#FF8000", id="hex-echoed"),
        pytest.param({FIELD_HEX: "nope"}, None, id="hex-invalid"),
        pytest.param({FIELD_RGB: [255, 128, 0]}, "#FF8000", id="rgb-converted"),
        pytest.param({FIELD_RGB: [999, 0, 0]}, None, id="rgb-invalid"),
        pytest.param({FIELD_HS: [0, 100]}, "#FF0000", id="hs-converted"),
        pytest.param({FIELD_HS: [999, 100]}, None, id="hs-invalid"),
        pytest.param({FIELD_COLOR_NAME: "red"}, "#FF0000", id="name-converted"),
        pytest.param({FIELD_COLOR_NAME: "not-a-color"}, None, id="name-invalid"),
        pytest.param({FIELD_XY: [0.4, 0.4]}, None, id="xy-has-no-source-hex"),
        pytest.param({FIELD_KELVIN: 4000}, None, id="kelvin-has-no-source-hex"),
    ],
)
def test_compute_source_hex(inputs: dict, expected: str | None) -> None:
    """Test source hex derivation per input shape."""
    assert compute_source_hex(inputs) == expected
