"""Color normalization for the Color helper.

The helper stores a canonical `(xy, kind, kelvin?)` tuple internally and
derives every attribute (hex/rgb/hs/kelvin) from it. This module dispatches
any accepted input shape to that canonical form using
`homeassistant.util.color`.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any

from homeassistant.util import color as color_util

from .const import (
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
    KIND_CHROMATIC,
    KIND_WHITE,
    MAX_KELVIN,
    MIN_KELVIN,
)


@dataclass(frozen=True)
class CanonicalColor:
    """Canonical color: chromaticity + chromatic/white kind + optional kelvin."""

    xy: tuple[float, float]
    kind: str  # KIND_CHROMATIC | KIND_WHITE
    kelvin: int | None = None  # set only when kind == KIND_WHITE


class ColorInputError(ValueError):
    """Raised when a color input is missing/ambiguous/out-of-range."""


def _strip_hex(hex_value: str) -> str:
    """Validate and strip a hex color string."""
    stripped = hex_value.strip().removeprefix("#")
    if len(stripped) != 6 or any(
        char not in "0123456789abcdefABCDEF" for char in stripped
    ):
        raise ColorInputError(f"Invalid hex color: {hex_value!r}")
    return stripped


def _hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
    """Convert a hex color string to an RGB tuple."""
    stripped = _strip_hex(hex_value)
    return int(stripped[0:2], 16), int(stripped[2:4], 16), int(stripped[4:6], 16)


def _validate_rgb(rgb: Any) -> tuple[int, int, int]:
    """Validate an RGB triplet."""
    if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
        raise ColorInputError(f"rgb_color must be a 3-element sequence, got {rgb!r}")
    try:
        r, g, b = (int(v) for v in rgb)
    except (TypeError, ValueError, OverflowError) as err:
        raise ColorInputError(
            f"rgb_color components must be numbers, got {rgb!r}"
        ) from err
    if not all(0 <= v <= 255 for v in (r, g, b)):
        raise ColorInputError("rgb_color components must be 0-255")
    return r, g, b


def _validate_hs(hs: Any) -> tuple[float, float]:
    """Validate a hue/saturation pair."""
    if not isinstance(hs, (list, tuple)) or len(hs) != 2:
        raise ColorInputError(f"hs_color must be a 2-element sequence, got {hs!r}")
    try:
        hue, sat = float(hs[0]), float(hs[1])
    except (TypeError, ValueError, OverflowError) as err:
        raise ColorInputError(
            f"hs_color components must be numbers, got {hs!r}"
        ) from err
    if not 0 <= hue <= 360:
        raise ColorInputError("hs_color hue must be 0-360")
    if not 0 <= sat <= 100:
        raise ColorInputError("hs_color saturation must be 0-100")
    return hue, sat


def valid_xy(x: float, y: float) -> bool:
    """Return True if (x, y) is a usable CIE chromaticity.

    y must be strictly positive: xy-to-RGB divides by y, and (0, 0) in
    particular would render as saturated blue via an epsilon denominator.
    """
    return isfinite(x) and isfinite(y) and 0.0 <= x <= 1.0 and y > 0.0 and x + y <= 1.0


def _validate_xy(xy: Any) -> tuple[float, float]:
    """Validate a CIE xy chromaticity pair."""
    if not isinstance(xy, (list, tuple)) or len(xy) != 2:
        raise ColorInputError(f"xy_color must be a 2-element sequence, got {xy!r}")
    try:
        x, y = float(xy[0]), float(xy[1])
    except (TypeError, ValueError, OverflowError) as err:
        raise ColorInputError(
            f"xy_color components must be numbers, got {xy!r}"
        ) from err
    if not valid_xy(x, y):
        raise ColorInputError("xy_color must be inside the CIE chromaticity triangle")
    return x, y


def _validate_kelvin(kelvin: Any) -> int:
    """Validate a color temperature in Kelvin."""
    try:
        value = int(kelvin)
    except (TypeError, ValueError, OverflowError) as err:
        raise ColorInputError(
            f"color_temp_kelvin must be an int, got {kelvin!r}"
        ) from err
    if not MIN_KELVIN <= value <= MAX_KELVIN:
        raise ColorInputError(
            f"color_temp_kelvin must be in [{MIN_KELVIN}, {MAX_KELVIN}]"
        )
    return value


COLOR_SHAPE_FIELDS = (
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
)


def normalize(inputs: dict[str, Any]) -> CanonicalColor:
    """Normalize one of the accepted color shapes to canonical form.

    Exactly one shape must be present. Mutual exclusivity is enforced here so
    callers can lean on a single error path.
    """
    present = {
        k: v for k, v in inputs.items() if k in COLOR_SHAPE_FIELDS and v is not None
    }
    if not present:
        raise ColorInputError(
            f"Provide exactly one of: {', '.join(sorted(COLOR_SHAPE_FIELDS))}"
        )
    if len(present) > 1:
        raise ColorInputError(
            f"Provide only one color input; got multiple: {sorted(present)}"
        )

    field, value = next(iter(present.items()))

    if field == FIELD_KELVIN:
        kelvin = _validate_kelvin(value)
        # White: store the chromaticity on the Planckian locus so chromatic
        # consumers still work; remember the kelvin for tunable-white targets.
        r, g, b = color_util.color_temperature_to_rgb(kelvin)
        x, y = color_util.color_RGB_to_xy(int(r), int(g), int(b))
        return CanonicalColor(xy=(x, y), kind=KIND_WHITE, kelvin=kelvin)

    if field == FIELD_HEX:
        r, g, b = _hex_to_rgb(str(value))
    elif field == FIELD_RGB:
        r, g, b = _validate_rgb(value)
    elif field == FIELD_HS:
        hue, sat = _validate_hs(value)
        r, g, b = color_util.color_hs_to_RGB(hue, sat)
    elif field == FIELD_XY:
        x, y = _validate_xy(value)
        return CanonicalColor(xy=(x, y), kind=KIND_CHROMATIC)
    else:  # FIELD_COLOR_NAME
        try:
            r, g, b = color_util.color_name_to_rgb(str(value))
        except ValueError as err:
            raise ColorInputError(f"Unknown color name: {value!r}") from err

    if (int(r), int(g), int(b)) == (0, 0, 0):
        # Zero intensity has no chromaticity; xy (0, 0) would render as blue.
        raise ColorInputError(
            "Pure black has no color value; store a color and use brightness 0"
        )
    x, y = color_util.color_RGB_to_xy(int(r), int(g), int(b))
    return CanonicalColor(xy=(x, y), kind=KIND_CHROMATIC)


def derive_rgb(canonical: CanonicalColor) -> tuple[int, int, int]:
    """Display-grade sRGB for the swatch/state. Uses kelvin when kind=white."""
    if canonical.kind == KIND_WHITE and canonical.kelvin is not None:
        r, g, b = color_util.color_temperature_to_rgb(canonical.kelvin)
        return int(r), int(g), int(b)
    return color_util.color_xy_to_RGB(*canonical.xy)


def derive_hs(canonical: CanonicalColor) -> tuple[float, float]:
    """Derive a hue/saturation pair from the canonical color."""
    r, g, b = derive_rgb(canonical)
    return color_util.color_RGB_to_hs(r, g, b)


def derive_kelvin(canonical: CanonicalColor) -> int | None:
    """Return the stored kelvin for kind=white; None for chromatic colors.

    McCamy's approximation will happily return a number for any chromatic xy,
    but for saturated colors that number is meaningless, so we only report a
    kelvin when the user explicitly picked a white.
    """
    if canonical.kind == KIND_WHITE and canonical.kelvin is not None:
        return canonical.kelvin
    return None


def derive_hex(canonical: CanonicalColor) -> str:
    """Derive an uppercase hex string from the canonical color."""
    r, g, b = derive_rgb(canonical)
    return "#" + color_util.color_rgb_to_hex(r, g, b).upper()


def compute_source_hex(inputs: dict[str, Any]) -> str | None:
    """Return the normalized sRGB hex of the user's input, if one exists.

    For inputs that map cleanly to a single sRGB triple (hex/rgb/hs/
    color_name), this preserves the pre-xy sRGB value, since the xy gamut
    round-trip is lossy. For xy/kelvin inputs there is no canonical
    "source hex" so we return None.
    """
    if inputs.get(FIELD_HEX) is not None:
        try:
            r, g, b = _hex_to_rgb(str(inputs[FIELD_HEX]))
        except ColorInputError:
            return None
    elif inputs.get(FIELD_RGB) is not None:
        try:
            r, g, b = _validate_rgb(inputs[FIELD_RGB])
        except ColorInputError:
            return None
    elif inputs.get(FIELD_HS) is not None:
        try:
            hue, sat = _validate_hs(inputs[FIELD_HS])
        except ColorInputError:
            return None
        r, g, b = color_util.color_hs_to_RGB(hue, sat)
    elif inputs.get(FIELD_COLOR_NAME) is not None:
        try:
            r, g, b = color_util.color_name_to_rgb(str(inputs[FIELD_COLOR_NAME]))
        except ValueError:
            return None
    else:
        return None

    return "#" + color_util.color_rgb_to_hex(int(r), int(g), int(b)).upper()
