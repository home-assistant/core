"""Volume conversion util functions."""


def liter_to_gallon(liter: float) -> float:
    """Convert a volume measurement in Liter to Gallon."""
    return liter * .2642


def gallon_to_liter(gallon: float) -> float:
    """Convert a volume measurement in Gallon to Liter."""
    return gallon * 3.785
