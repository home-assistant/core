"""Test Home Assistant scaling utils."""

import math

from homeassistant.util.percentage import (
    scale_ranged_value_to_int_range,
    scale_to_ranged_value,
)


async def test_ranged_value_to_int_range_large() -> None:
    """Test a large range of low and high values convert a single value to a percentage."""
    source_range = (1, 255)
    dest_range = (1, 100)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 255) == 100
    assert scale_ranged_value_to_int_range(source_range, dest_range, 127) == 49
    assert scale_ranged_value_to_int_range(source_range, dest_range, 10) == 3
    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 0


async def test_scale_to_ranged_value_large() -> None:
    """Test a large range of low and high values convert an int to a single value."""
    source_range = (1, 100)
    dest_range = (1, 255)

    assert scale_to_ranged_value(source_range, dest_range, 100) == 255
    assert scale_to_ranged_value(source_range, dest_range, 50) == 127.5
    assert scale_to_ranged_value(source_range, dest_range, 4) == 10.2

    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 100)) == 255
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 50)) == 128
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 4)) == 11


async def test_scale_ranged_value_to_int_range_small() -> None:
    """Test a small range of low and high values convert a single value to a percentage."""
    source_range = (1, 6)
    dest_range = (1, 100)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 16
    assert scale_ranged_value_to_int_range(source_range, dest_range, 2) == 33
    assert scale_ranged_value_to_int_range(source_range, dest_range, 3) == 50
    assert scale_ranged_value_to_int_range(source_range, dest_range, 4) == 66
    assert scale_ranged_value_to_int_range(source_range, dest_range, 5) == 83
    assert scale_ranged_value_to_int_range(source_range, dest_range, 6) == 100


async def test_scale_to_ranged_value_small() -> None:
    """Test a small range of low and high values convert an int to a single value."""
    source_range = (1, 100)
    dest_range = (1, 6)

    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 16)) == 1
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 33)) == 2
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 50)) == 3
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 66)) == 4
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 83)) == 5
    assert math.ceil(scale_to_ranged_value(source_range, dest_range, 100)) == 6


async def test_scale_ranged_value_to_int_range_starting_at_one() -> None:
    """Test a range that starts with 1."""
    source_range = (1, 4)
    dest_range = (1, 100)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 25
    assert scale_ranged_value_to_int_range(source_range, dest_range, 2) == 50
    assert scale_ranged_value_to_int_range(source_range, dest_range, 3) == 75
    assert scale_ranged_value_to_int_range(source_range, dest_range, 4) == 100


async def test_scale_ranged_value_to_int_range_starting_high() -> None:
    """Test a range that does not start with 1."""
    source_range = (101, 255)
    dest_range = (1, 100)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 101) == 0
    assert scale_ranged_value_to_int_range(source_range, dest_range, 139) == 25
    assert scale_ranged_value_to_int_range(source_range, dest_range, 178) == 50
    assert scale_ranged_value_to_int_range(source_range, dest_range, 217) == 75
    assert scale_ranged_value_to_int_range(source_range, dest_range, 255) == 100


async def test_scale_ranged_value_to_scaled_range_starting_zero() -> None:
    """Test a range that starts with 0."""
    source_range = (0, 3)
    dest_range = (1, 100)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 0) == 25
    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 50
    assert scale_ranged_value_to_int_range(source_range, dest_range, 2) == 75
    assert scale_ranged_value_to_int_range(source_range, dest_range, 3) == 100

    assert scale_to_ranged_value(source_range, dest_range, 0) == 25.0
    assert scale_to_ranged_value(source_range, dest_range, 1) == 50.0
    assert scale_to_ranged_value(source_range, dest_range, 2) == 75.0
    assert scale_to_ranged_value(source_range, dest_range, 3) == 100.0

    assert scale_ranged_value_to_int_range(dest_range, source_range, 25.0) == 0
    assert scale_ranged_value_to_int_range(dest_range, source_range, 50.0) == 1
    assert scale_ranged_value_to_int_range(dest_range, source_range, 75.0) == 2
    assert scale_ranged_value_to_int_range(dest_range, source_range, 100.0) == 3

    assert scale_to_ranged_value(dest_range, source_range, 25.0) == 0.0
    assert scale_to_ranged_value(dest_range, source_range, 50.0) == 1.0
    assert scale_to_ranged_value(dest_range, source_range, 75.0) == 2.0
    assert scale_to_ranged_value(dest_range, source_range, 100.0) == 3.0


async def test_scale_ranged_value_to_int_range_starting_high_with_offset() -> None:
    """Test a ranges that do not start with 1."""
    source_range = (101, 255)
    dest_range = (101, 200)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 101) == 100
    assert scale_ranged_value_to_int_range(source_range, dest_range, 139) == 125
    assert scale_ranged_value_to_int_range(source_range, dest_range, 178) == 150
    assert scale_ranged_value_to_int_range(source_range, dest_range, 217) == 175
    assert scale_ranged_value_to_int_range(source_range, dest_range, 255) == 200


async def test_scale_ranged_value_to_int_range_starting_zero_with_offset() -> None:
    """Test a range that starts with 0 and an other starting high."""
    source_range = (0, 3)
    dest_range = (101, 200)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 0) == 125
    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 150
    assert scale_ranged_value_to_int_range(source_range, dest_range, 2) == 175
    assert scale_ranged_value_to_int_range(source_range, dest_range, 3) == 200


async def test_scale_ranged_value_to_int_range_starting_zero_with_zero_offset() -> None:
    """Test a ranges that start with 0.

    In case a range starts with 0, this means value 0 is the first value,
    and the values shift -1.
    """
    source_range = (0, 3)
    dest_range = (0, 7)

    assert scale_ranged_value_to_int_range(source_range, dest_range, 0) == 1
    assert scale_ranged_value_to_int_range(source_range, dest_range, 1) == 3
    assert scale_ranged_value_to_int_range(source_range, dest_range, 2) == 5
    assert scale_ranged_value_to_int_range(source_range, dest_range, 3) == 7

    assert scale_to_ranged_value(source_range, dest_range, 0) == 1.0
    assert scale_to_ranged_value(source_range, dest_range, 1) == 3.0
    assert scale_to_ranged_value(source_range, dest_range, 2) == 5.0
    assert scale_to_ranged_value(source_range, dest_range, 3) == 7.0

    assert scale_ranged_value_to_int_range(dest_range, source_range, 1) == 0
    assert scale_ranged_value_to_int_range(dest_range, source_range, 3) == 1
    assert scale_ranged_value_to_int_range(dest_range, source_range, 5) == 2
    assert scale_ranged_value_to_int_range(dest_range, source_range, 7) == 3

    assert scale_to_ranged_value(dest_range, source_range, 1.0) == 0
    assert scale_to_ranged_value(dest_range, source_range, 3.0) == 1
    assert scale_to_ranged_value(dest_range, source_range, 5.0) == 2
    assert scale_to_ranged_value(dest_range, source_range, 7.0) == 3
