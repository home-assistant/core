"""Provide integration utilities."""
from __future__ import annotations


def renormalize(
    number: float, from_range: tuple[float, float], to_range: tuple[float, float]
) -> float:
    """Change value from from_range to to_range."""
    delta1 = from_range[1] - from_range[0]
    delta2 = to_range[1] - to_range[0]
    return (delta2 * (number - from_range[0]) / delta1) + to_range[0]
