"""Helper functions for Philips Hue v2."""
from __future__ import annotations


def normalize_hue_brightness(brightness: float | None) -> float | None:
    """Return calculated brightness values."""
    if brightness is not None:
        # Hue uses a range of [0, 100] to control brightness.
        brightness = float((brightness / 255) * 100)

    return brightness


def normalize_hue_transition(transition: float | None) -> float | None:
    """Return rounded transition values."""
    if transition is not None:
        # hue transition duration is in milliseconds and round them to 100ms
        transition = int(round(transition, 1) * 1000)

    return transition


def normalize_hue_colortemp(colortemp: int | None) -> int | None:
    """Return color temperature within Hue's ranges."""
    if colortemp is not None:
        # Hue only accepts a range between 153..500
        colortemp = min(colortemp, 500)
        colortemp = max(colortemp, 153)
    return colortemp
