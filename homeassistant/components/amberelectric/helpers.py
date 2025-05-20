"""Formatting helpers used to convert things."""

from amberelectric.models.price_descriptor import PriceDescriptor

descriptor_map: dict[str, str] = {
    PriceDescriptor.SPIKE: "spike",
    PriceDescriptor.HIGH: "high",
    PriceDescriptor.NEUTRAL: "neutral",
    PriceDescriptor.LOW: "low",
    PriceDescriptor.VERYLOW: "very_low",
    PriceDescriptor.EXTREMELYLOW: "extremely_low",
    PriceDescriptor.NEGATIVE: "negative",
}


def normalize_descriptor(descriptor: PriceDescriptor | None) -> str | None:
    """Return the snake case versions of descriptor names. Returns None if the name is not recognized."""
    if descriptor in descriptor_map:
        return descriptor_map[descriptor]
    return None
