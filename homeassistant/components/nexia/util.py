"""Utils for Nexia / Trane XL Thermostats."""


def percent_conv(val):
    """Convert an actual percentage (0.0-1.0) to 0-100 scale."""
    return round(val * 100.0, 1)
