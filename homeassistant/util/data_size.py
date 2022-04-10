"""Data size util functions."""
import numbers

from homeassistant.const import (
    DATA_BYTES,
    DATA_EXABYTES,
    DATA_EXBIBYTES,
    DATA_GIBIBYTES,
    DATA_GIGABYTES,
    DATA_KIBIBYTES,
    DATA_KILOBYTES,
    DATA_MEBIBYTES,
    DATA_MEGABYTES,
    DATA_PEBIBYTES,
    DATA_PETABYTES,
    DATA_SIZE,
    DATA_TEBIBYTES,
    DATA_TERABYTES,
    DATA_YOBIBYTES,
    DATA_YOTTABYTES,
    DATA_ZEBIBYTES,
    DATA_ZETTABYTES,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS_SI = [
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
    DATA_TERABYTES,
    DATA_PETABYTES,
    DATA_EXABYTES,
    DATA_ZETTABYTES,
    DATA_YOTTABYTES,
]

VALID_UNITS_IEC = [
    DATA_BYTES,
    DATA_KIBIBYTES,
    DATA_MEBIBYTES,
    DATA_GIBIBYTES,
    DATA_TEBIBYTES,
    DATA_PEBIBYTES,
    DATA_EXBIBYTES,
    DATA_ZEBIBYTES,
    DATA_YOBIBYTES,
]


def convert(value: float, unit_input: str, unit_output: str) -> float:
    """Convert one unit of measurement to another."""

    # Check if provided units are valid in this context
    if unit_input not in VALID_UNITS_SI and unit_input not in VALID_UNITS_IEC:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_input, DATA_SIZE))
    if unit_output not in VALID_UNITS_SI and unit_output not in VALID_UNITS_IEC:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_output, DATA_SIZE))

    if not isinstance(value, numbers.Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_input == unit_output:
        return value

    result = value

    # First convert the input down until we are at bytes
    if unit_input in VALID_UNITS_SI:
        index = VALID_UNITS_SI.index(unit_input)
        factor = pow(1000, index)
    else:
        index = VALID_UNITS_IEC.index(unit_input)
        factor = pow(1024, index)

    result *= factor

    # Now convert the bytes up to the target unit, unless target is bytes
    if unit_output != DATA_BYTES:
        if unit_output in VALID_UNITS_SI:
            index = VALID_UNITS_SI.index(unit_output)
            factor = pow(1000, index)
        else:
            index = VALID_UNITS_IEC.index(unit_output)
            factor = pow(1024, index)

        result /= factor

    return result
