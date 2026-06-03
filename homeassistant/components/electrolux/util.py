"""Utility functions used by the Electrolux integration."""

from homeassistant.helpers.entity import EntityDescription


def round_to_multiple_of_step(value: float, step: float) -> float:
    """Utility function for rounding a value to the closest multiple of a step."""
    return round(value / step) * step


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


def get_submodule_entity_key(submodule: str, description: EntityDescription) -> str:
    """Get the entity key for a submodule."""
    return f"{convert_to_snake_case(submodule)}_{description.key}"


def get_submodule_translation_key(
    submodule: str, description: EntityDescription
) -> str:
    """Get the translation key for a submodule."""
    return f"{convert_to_snake_case(submodule)}_{description.translation_key}"
