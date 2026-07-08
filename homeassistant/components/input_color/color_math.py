"""Color normalization for the Input Color helper."""

from dataclasses import dataclass
from typing import Any

from homeassistant.util import color as color_util

FIELD_COLOR_NAME = "color_name"
FIELD_HEX = "hex_value"
FIELD_HS = "hs_color"
FIELD_KELVIN = "color_temp_kelvin"
FIELD_RGB = "rgb_color"
FIELD_XY = "xy_color"

KIND_CHROMATIC = "chromatic"
KIND_WHITE = "white"

MIN_KELVIN = 1000
MAX_KELVIN = 20000


@dataclass(frozen=True)
class CanonicalColor:
    """Canonical color: chromaticity, kind, and optional kelvin value."""

    xy: tuple[float, float]
    kind: str
    kelvin: int | None = None


class ColorInputError(ValueError):
    """Raised when a color input is missing, ambiguous, or out of range."""


def _strip_hex(hex_value: str) -> str:
    """Strip and validate a hex color."""
    hex_str = hex_value.strip().lstrip("#")
    if len(hex_str) != 6 or any(
        char not in "0123456789abcdefABCDEF" for char in hex_str
    ):
        raise ColorInputError(f"Invalid hex color: {hex_value!r}")
    return hex_str


def _hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
    """Convert a hex color to RGB."""
    hex_str = _strip_hex(hex_value)
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


def _validate_rgb(rgb: Any) -> tuple[int, int, int]:
    """Validate an RGB value."""
    if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
        raise ColorInputError(f"rgb_color must be a 3-element sequence, got {rgb!r}")
    r, g, b = (int(value) for value in rgb)
    if not all(0 <= value <= 255 for value in (r, g, b)):
        raise ColorInputError("rgb_color components must be 0-255")
    return r, g, b


def _validate_hs(hs: Any) -> tuple[float, float]:
    """Validate an HS value."""
    if not isinstance(hs, (list, tuple)) or len(hs) != 2:
        raise ColorInputError(f"hs_color must be a 2-element sequence, got {hs!r}")
    h, s = float(hs[0]), float(hs[1])
    if not 0 <= h <= 360:
        raise ColorInputError("hs_color hue must be 0-360")
    if not 0 <= s <= 100:
        raise ColorInputError("hs_color saturation must be 0-100")
    return h, s


def _validate_xy(xy: Any) -> tuple[float, float]:
    """Validate a CIE xy value."""
    if not isinstance(xy, (list, tuple)) or len(xy) != 2:
        raise ColorInputError(f"xy_color must be a 2-element sequence, got {xy!r}")
    x, y = float(xy[0]), float(xy[1])
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ColorInputError("xy_color components must be in [0, 1]")
    return x, y


def _validate_kelvin(kelvin: Any) -> int:
    """Validate a kelvin color temperature value."""
    try:
        kelvin_int = int(kelvin)
    except (TypeError, ValueError) as err:
        raise ColorInputError(
            f"color_temp_kelvin must be an int, got {kelvin!r}"
        ) from err
    if not MIN_KELVIN <= kelvin_int <= MAX_KELVIN:
        raise ColorInputError(
            f"color_temp_kelvin must be in [{MIN_KELVIN}, {MAX_KELVIN}]"
        )
    return kelvin_int


def normalize(inputs: dict[str, Any]) -> CanonicalColor:
    """Normalize exactly one accepted color shape to canonical form."""
    keys = {
        FIELD_HEX,
        FIELD_RGB,
        FIELD_HS,
        FIELD_XY,
        FIELD_KELVIN,
        FIELD_COLOR_NAME,
    }
    present = {
        key: value for key, value in inputs.items() if key in keys and value is not None
    }
    if not present:
        raise ColorInputError(f"Provide exactly one of: {', '.join(sorted(keys))}")
    if len(present) > 1:
        raise ColorInputError(
            f"Provide only one color input; got multiple: {sorted(present)}"
        )

    field, value = next(iter(present.items()))

    if field == FIELD_KELVIN:
        kelvin = _validate_kelvin(value)
        r, g, b = color_util.color_temperature_to_rgb(kelvin)
        x, y = color_util.color_RGB_to_xy(int(r), int(g), int(b))
        return CanonicalColor(xy=(x, y), kind=KIND_WHITE, kelvin=kelvin)

    if field == FIELD_HEX:
        r, g, b = _hex_to_rgb(str(value))
    elif field == FIELD_RGB:
        r, g, b = _validate_rgb(value)
    elif field == FIELD_HS:
        h, s = _validate_hs(value)
        r, g, b = color_util.color_hs_to_RGB(h, s)
    elif field == FIELD_XY:
        x, y = _validate_xy(value)
        return CanonicalColor(xy=(x, y), kind=KIND_CHROMATIC)
    elif field == FIELD_COLOR_NAME:
        try:
            r, g, b = color_util.color_name_to_rgb(str(value))
        except ValueError as err:
            raise ColorInputError(f"Unknown color name: {value!r}") from err
    else:  # pragma: no cover
        raise ColorInputError(f"Unhandled color input: {field}")

    x, y = color_util.color_RGB_to_xy(int(r), int(g), int(b))
    return CanonicalColor(xy=(x, y), kind=KIND_CHROMATIC)


def derive_rgb(canonical: CanonicalColor) -> tuple[int, int, int]:
    """Return display-grade sRGB for the color."""
    if canonical.kind == KIND_WHITE and canonical.kelvin is not None:
        r, g, b = color_util.color_temperature_to_rgb(canonical.kelvin)
        return int(r), int(g), int(b)
    return color_util.color_xy_to_RGB(*canonical.xy)


def derive_hs(canonical: CanonicalColor) -> tuple[float, float]:
    """Return HS for the color."""
    r, g, b = derive_rgb(canonical)
    return color_util.color_RGB_to_hs(r, g, b)


def derive_kelvin(canonical: CanonicalColor) -> int | None:
    """Return stored kelvin for white colors."""
    if canonical.kind == KIND_WHITE and canonical.kelvin is not None:
        return canonical.kelvin
    return None


def derive_hex(canonical: CanonicalColor) -> str:
    """Return a hex string for the color."""
    r, g, b = derive_rgb(canonical)
    return "#" + color_util.color_rgb_to_hex(r, g, b).upper()


def compute_source_hex(inputs: dict[str, Any]) -> str | None:
    """Return the literal hex equivalent of the input, if one exists."""
    if FIELD_HEX in inputs and inputs[FIELD_HEX] is not None:
        try:
            r, g, b = _hex_to_rgb(str(inputs[FIELD_HEX]))
        except ColorInputError:
            return None
    elif FIELD_RGB in inputs and inputs[FIELD_RGB] is not None:
        try:
            r, g, b = _validate_rgb(inputs[FIELD_RGB])
        except ColorInputError:
            return None
    elif FIELD_HS in inputs and inputs[FIELD_HS] is not None:
        try:
            h, s = _validate_hs(inputs[FIELD_HS])
        except ColorInputError:
            return None
        r, g, b = color_util.color_hs_to_RGB(h, s)
    elif FIELD_COLOR_NAME in inputs and inputs[FIELD_COLOR_NAME] is not None:
        try:
            r, g, b = color_util.color_name_to_rgb(str(inputs[FIELD_COLOR_NAME]))
        except ValueError:
            return None
    else:
        return None

    return "#" + color_util.color_rgb_to_hex(int(r), int(g), int(b)).upper()
