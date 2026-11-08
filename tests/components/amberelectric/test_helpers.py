"""Test formatters."""

from amberelectric.models.price_descriptor import PriceDescriptor
import pytest

from homeassistant.components.amberelectric.helpers import (
    format_cents_to_dollars,
    normalize_descriptor,
)


def test_normalize_descriptor() -> None:
    """Test normalizing descriptors works correctly."""
    assert normalize_descriptor(None) is None
    assert normalize_descriptor(PriceDescriptor.NEGATIVE) == "negative"
    assert normalize_descriptor(PriceDescriptor.EXTREMELYLOW) == "extremely_low"
    assert normalize_descriptor(PriceDescriptor.VERYLOW) == "very_low"
    assert normalize_descriptor(PriceDescriptor.LOW) == "low"
    assert normalize_descriptor(PriceDescriptor.NEUTRAL) == "neutral"
    assert normalize_descriptor(PriceDescriptor.HIGH) == "high"
    assert normalize_descriptor(PriceDescriptor.SPIKE) == "spike"


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        pytest.param(8.8, 8.8 / 100, id="general"),
        pytest.param(4.4, 4.4 / 100, id="controlled_load"),
        pytest.param(1.1, 1.1 / 100, id="feed_in"),
        pytest.param(0.09619, 0.0009619, id="near_zero"),
        pytest.param(-0.09619, -0.0009619, id="near_zero_negative"),
    ],
)
def test_format_cents_to_dollars(cents: float, expected: float) -> None:
    """Test cents-to-dollars conversion preserves source precision."""
    assert format_cents_to_dollars(cents) == expected
