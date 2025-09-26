"""Provide integration utilities."""

from __future__ import annotations

XY_COLOR_FACTOR = 65536


def renormalize(
    number: float, from_range: tuple[float, float], to_range: tuple[float, float]
) -> float:
    """Change value from from_range to to_range."""
    delta1 = from_range[1] - from_range[0]
    delta2 = to_range[1] - to_range[0]
    return (delta2 * (number - from_range[0]) / delta1) + to_range[0]


def convert_to_matter_hs(hass_hs: tuple[float, float]) -> tuple[float, float]:
    """Convert Home Assistant HS to Matter HS."""

    return (
        hass_hs[0] / 360 * 254,
        renormalize(hass_hs[1], (0, 100), (0, 254)),
    )


def convert_to_hass_hs(matter_hs: tuple[float, float]) -> tuple[float, float]:
    """Convert Matter HS to Home Assistant HS."""

    return (
        matter_hs[0] * 360 / 254,
        renormalize(matter_hs[1], (0, 254), (0, 100)),
    )


def convert_to_matter_xy(hass_xy: tuple[float, float]) -> tuple[float, float]:
    """Convert Home Assistant XY to Matter XY."""

    return (hass_xy[0] * XY_COLOR_FACTOR, hass_xy[1] * XY_COLOR_FACTOR)


def convert_to_hass_xy(matter_xy: tuple[float, float]) -> tuple[float, float]:
    """Convert Matter XY to Home Assistant XY."""

    return (matter_xy[0] / XY_COLOR_FACTOR, matter_xy[1] / XY_COLOR_FACTOR)
