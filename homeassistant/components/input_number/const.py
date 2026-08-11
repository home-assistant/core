"""Constants for the input_number integration."""

from enum import StrEnum


class InputNumberEntityStateAttribute(StrEnum):
    """State attributes for input number entities."""

    INITIAL = "initial"
    EDITABLE = "editable"
