"""codes.py: Shared IR command resolution utilities for the LG infrared integration."""
from enum import Enum


def resolve_numeric_code(base_code: Enum, tuner: str) -> Enum:
    """Resolve NUM_X to tuner-specific variant within same codeset."""
    if not base_code.name.startswith("NUM_"):
        return base_code

    enum_cls = type(base_code)
    code_name = f"{tuner.upper()}_{base_code.name}"
    return enum_cls.__members__.get(code_name, base_code)
