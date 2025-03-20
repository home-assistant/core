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


def closest_value(range_tuple, step, target):
    """Find the closest integer value to the target within a specified range and step.

    :param range_tuple: Tuple with the start and end of the range
    :param step: Step between values
    :param target: Target value
    :return: Closest value
    """
    # Generate values in the specified range with the given step
    values = list(range(range_tuple[0], range_tuple[1] + step, step))
    values.append(range_tuple[1])  # Ensure maximum value is included

    # Find the closest value
    return min(values, key=lambda v: abs(v - target))
