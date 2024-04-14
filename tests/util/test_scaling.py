"""Test Home Assistant scaling utils."""

import math

import pytest

from homeassistant.util.percentage import (
    scale_ranged_value_to_int_range,
    scale_to_ranged_value,
)


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (255, 100),
        (127, 49),
        (10, 3),
        (1, 0),
    ],
)
async def test_ranged_value_to_int_range_large(
    input_val: float, output_val: int
) -> None:
    """Test a large range of low and high values convert a single value to a percentage."""
    source_range = (1, 255)
    dest_range = (1, 100)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_val", "math_ceil"),
    [
        (100, 255, 255),
        (50, 127.5, 128),
        (4, 10.2, 11),
    ],
)
async def test_scale_to_ranged_value_large(
    input_val: float, output_val: float, math_ceil: int
) -> None:
    """Test a large range of low and high values convert an int to a single value."""
    source_range = (1, 100)
    dest_range = (1, 255)

    assert scale_to_ranged_value(source_range, dest_range, input_val) == output_val

    assert (
        math.ceil(scale_to_ranged_value(source_range, dest_range, input_val))
        == math_ceil
    )


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (1, 16),
        (2, 33),
        (3, 50),
        (4, 66),
        (5, 83),
        (6, 100),
    ],
)
async def test_scale_ranged_value_to_int_range_small(
    input_val: float, output_val: int
) -> None:
    """Test a small range of low and high values convert a single value to a percentage."""
    source_range = (1, 6)
    dest_range = (1, 100)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (16, 1),
        (33, 2),
        (50, 3),
        (66, 4),
        (83, 5),
        (100, 6),
    ],
)
async def test_scale_to_ranged_value_small(input_val: float, output_val: int) -> None:
    """Test a small range of low and high values convert an int to a single value."""
    source_range = (1, 100)
    dest_range = (1, 6)

    assert (
        math.ceil(scale_to_ranged_value(source_range, dest_range, input_val))
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (1, 25),
        (2, 50),
        (3, 75),
        (4, 100),
    ],
)
async def test_scale_ranged_value_to_int_range_starting_at_one(
    input_val: float, output_val: int
) -> None:
    """Test a range that starts with 1."""
    source_range = (1, 4)
    dest_range = (1, 100)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (101, 0),
        (139, 25),
        (178, 50),
        (217, 75),
        (255, 100),
    ],
)
async def test_scale_ranged_value_to_int_range_starting_high(
    input_val: float, output_val: int
) -> None:
    """Test a range that does not start with 1."""
    source_range = (101, 255)
    dest_range = (1, 100)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_int", "output_float"),
    [
        (0.0, 25, 25.0),
        (1.0, 50, 50.0),
        (2.0, 75, 75.0),
        (3.0, 100, 100.0),
    ],
)
async def test_scale_ranged_value_to_scaled_range_starting_zero(
    input_val: float, output_int: int, output_float: float
) -> None:
    """Test a range that starts with 0."""
    source_range = (0, 3)
    dest_range = (1, 100)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_int
    )
    assert scale_to_ranged_value(source_range, dest_range, input_val) == output_float
    assert scale_ranged_value_to_int_range(
        dest_range, source_range, output_float
    ) == int(input_val)
    assert scale_to_ranged_value(dest_range, source_range, output_float) == input_val


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (101, 100),
        (139, 125),
        (178, 150),
        (217, 175),
        (255, 200),
    ],
)
async def test_scale_ranged_value_to_int_range_starting_high_with_offset(
    input_val: float, output_val: int
) -> None:
    """Test a ranges that do not start with 1."""
    source_range = (101, 255)
    dest_range = (101, 200)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_val"),
    [
        (0, 125),
        (1, 150),
        (2, 175),
        (3, 200),
    ],
)
async def test_scale_ranged_value_to_int_range_starting_zero_with_offset(
    input_val: float, output_val: int
) -> None:
    """Test a range that starts with 0 and an other starting high."""
    source_range = (0, 3)
    dest_range = (101, 200)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_val
    )


@pytest.mark.parametrize(
    ("input_val", "output_int", "output_float"),
    [
        (0.0, 1, 1.0),
        (1.0, 3, 3.0),
        (2.0, 5, 5.0),
        (3.0, 7, 7.0),
    ],
)
async def test_scale_ranged_value_to_int_range_starting_zero_with_zero_offset(
    input_val: float, output_int: int, output_float: float
) -> None:
    """Test a ranges that start with 0.

    In case a range starts with 0, this means value 0 is the first value,
    and the values shift -1.
    """
    source_range = (0, 3)
    dest_range = (0, 7)

    assert (
        scale_ranged_value_to_int_range(source_range, dest_range, input_val)
        == output_int
    )
    assert scale_to_ranged_value(source_range, dest_range, input_val) == output_float
    assert scale_ranged_value_to_int_range(dest_range, source_range, output_int) == int(
        input_val
    )
    assert scale_to_ranged_value(dest_range, source_range, output_float) == input_val
