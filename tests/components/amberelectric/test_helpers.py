"""Test formatters."""

from amberelectric.models.price_descriptor import PriceDescriptor

from homeassistant.components.amberelectric.helpers import normalize_descriptor


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
