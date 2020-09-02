"""Utils for Nexia / Trane XL Thermostats."""

from homeassistant.const import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
)


def is_invalid_auth_code(http_status_code):
    """HTTP status codes that mean invalid auth."""
    if (
        HTTP_BAD_REQUEST =< http_status_code < HTTP_INTERNAL_SERVER_ERROR
        and http_status_code != HTTP_NOT_FOUND
    ):
        return True

    return False


def percent_conv(val):
    """Convert an actual percentage (0.0-1.0) to 0-100 scale."""
    return round(val * 100.0, 1)
