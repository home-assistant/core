"""Test input_color color math."""

import pytest

from homeassistant.components.input_color.color_math import (
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
    KIND_CHROMATIC,
    KIND_WHITE,
    ColorInputError,
    compute_source_hex,
    derive_hex,
    derive_kelvin,
    derive_rgb,
    normalize,
)


def test_normalize_hex() -> None:
    """Test normalizing a hex color."""
    canonical = normalize({FIELD_HEX: "#FF8000"})

    assert canonical.kind == KIND_CHROMATIC
    assert derive_hex(canonical) == "#FF8201"
    assert derive_kelvin(canonical) is None
    assert compute_source_hex({FIELD_HEX: "#ff8000"}) == "#FF8000"


def test_normalize_rgb_hs_and_name_source_hex() -> None:
    """Test normalizing RGB, HS, and color names."""
    assert compute_source_hex({FIELD_RGB: [255, 0, 0]}) == "#FF0000"
    assert compute_source_hex({FIELD_HS: [120, 100]}) == "#00FF00"
    assert compute_source_hex({FIELD_COLOR_NAME: "blue"}) == "#0000FF"


def test_normalize_xy() -> None:
    """Test normalizing CIE xy."""
    canonical = normalize({FIELD_XY: [0.5, 0.4]})

    assert canonical.kind == KIND_CHROMATIC
    assert canonical.xy == (0.5, 0.4)
    assert compute_source_hex({FIELD_XY: [0.5, 0.4]}) is None


def test_normalize_kelvin() -> None:
    """Test normalizing a kelvin color temperature."""
    canonical = normalize({FIELD_KELVIN: 2700})

    assert canonical.kind == KIND_WHITE
    assert canonical.kelvin == 2700
    assert derive_kelvin(canonical) == 2700
    assert compute_source_hex({FIELD_KELVIN: 2700}) is None
    assert len(derive_rgb(canonical)) == 3


@pytest.mark.parametrize(
    "color_input",
    [
        {},
        {FIELD_HEX: "#NOPE"},
        {FIELD_HEX: "#FFFFFF", FIELD_RGB: [255, 255, 255]},
        {FIELD_RGB: [256, 0, 0]},
        {FIELD_HS: [361, 100]},
        {FIELD_XY: [1.2, 0.4]},
        {FIELD_KELVIN: 999},
        {FIELD_COLOR_NAME: "not-a-color"},
    ],
)
def test_normalize_rejects_invalid_inputs(color_input) -> None:
    """Test invalid color input validation."""
    with pytest.raises(ColorInputError):
        normalize(color_input)
