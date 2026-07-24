"""Utility functions used by the Electrolux integration."""


def round_to_valid_step_int(value: float, minimum: int, step: int) -> int:
    """Utility function for rounding a value to the closest multiple of a step."""
    return round((value - minimum) / step) * step + minimum


def convert_to_snake_case(x: str) -> str:
    """Converts a string to snake case."""
    lower_case = x.lower()
    return "".join([_convert_char_to_snake_case(char) for char in lower_case])


def _convert_char_to_snake_case(char: str) -> str:
    if char.isspace():
        return "_"
    return char
