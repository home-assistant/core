"""Utils for Nexia / Trane XL Thermostats."""

from http import HTTPStatus


def is_invalid_auth_code(http_status_code):
    """HTTP status codes that mean invalid auth."""
    if http_status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        return True

    return False


def percent_conv(val):
    """Convert an actual percentage (0.0-1.0) to 0-100 scale."""
    if val is None:
        return None
    return round(val * 100.0, 1)
