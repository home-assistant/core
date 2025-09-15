"""Formatting helpers used to convert things."""

from amberelectric.models.price_descriptor import PriceDescriptor

DESCRIPTOR_MAP: dict[str, str] = {
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
    if descriptor in DESCRIPTOR_MAP:
        return DESCRIPTOR_MAP[descriptor]
    return None


def format_cents_to_dollars(cents: float) -> float:
    """Return a formatted conversion from cents to dollars."""
    return round(cents / 100, 2)
