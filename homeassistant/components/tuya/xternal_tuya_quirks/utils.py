"""Common utility functions for Tuya quirks."""


def scale_value(value: int, step: float, scale: float) -> float:
    """Official scaling function from Tuya.

    See https://support.tuya.com/en/help/_detail/Kadi66s463e2q
    """
    return step * value / (10**scale)


def scale_value_back(value: float, step: float, scale: float) -> int:
    """Official scaling function from Tuya.

    See https://support.tuya.com/en/help/_detail/Kadi66s463e2q
    """

    return int(value * (10**scale) / step)
