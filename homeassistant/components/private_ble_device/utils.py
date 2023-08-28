"""Utilities for bluetooth devices."""
from typing import cast

MAX_THEORETICAL_DISTANCE = 400.0


def calculate_distance_meters(power: int, rssi: int) -> float | None:
    """Calculate the distance in meters between the scanner and the device."""
    if rssi == 0 or power == 0:
        return None
    if (ratio := rssi * 1.0 / power) < 1.0:
        distance = pow(ratio, 10)
    else:
        distance = cast(float, 0.89976 * pow(ratio, 7.7095) + 0.111)
    return min(distance, MAX_THEORETICAL_DISTANCE)
