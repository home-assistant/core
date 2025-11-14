"""Test the low-level curve helper functionality."""

from homeassistant.components.curve.helpers import interpolate_curve
from homeassistant.components.curve.models import CurveSegment


def test_avoid_zero_div() -> None:
    """Test that `interpolate_curve` won't end up doing zero division if x0 == x1."""
    segs = [CurveSegment(x0=1, x1=1, y0=1, y1=1)]
    assert interpolate_curve(1, segs) == 1
