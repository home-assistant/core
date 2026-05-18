"""Utility functions used by the Electrolux integration."""


def convert_to_snake_case(x: str) -> str:
    """Converts a string to snake case."""
    lower_case = x.lower()
    return "".join([_convert_char_to_snake_case(char) for char in lower_case])


def _convert_char_to_snake_case(char: str) -> str:
    if char.isspace():
        return "_"
    return char
