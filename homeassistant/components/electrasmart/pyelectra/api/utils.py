"""Helpers for the Electra API client."""

from math import floor, pow
from random import randint


def generate_imei() -> str:
    """Generate a random IMEI for a new device registration."""
    minimum = int(pow(10, 7))
    maximum = int(pow(10, 8) - 1)
    return f"2b950000{floor(randint(minimum, maximum))!s}"
