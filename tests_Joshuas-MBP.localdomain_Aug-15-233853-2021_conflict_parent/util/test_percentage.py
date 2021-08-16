"""Test Home Assistant percentage conversions."""

import math

import pytest

from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

SPEED_LOW = "low"
SPEED_MEDIUM = "medium"
SPEED_HIGH = "high"

SPEED_1 = SPEED_LOW
SPEED_2 = SPEED_MEDIUM
SPEED_3 = SPEED_HIGH
SPEED_4 = "very_high"
SPEED_5 = "storm"
SPEED_6 = "hurricane"
SPEED_7 = "solar_wind"

LEGACY_ORDERED_LIST = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
SMALL_ORDERED_LIST = [SPEED_1, SPEED_2, SPEED_3, SPEED_4]
LARGE_ORDERED_LIST = [SPEED_1, SPEED_2, SPEED_3, SPEED_4, SPEED_5, SPEED_6, SPEED_7]


async def test_ordered_list_percentage_round_trip():
    """Test we can round trip."""
    for ordered_list in (SMALL_ORDERED_LIST, LARGE_ORDERED_LIST):
        for i in range(1, 100):
            ordered_list_item_to_percentage(
                ordered_list, percentage_to_ordered_list_item(ordered_list, i)
            ) == i


async def test_ordered_list_item_to_percentage():
    """Test percentage of an item in an ordered list."""

    assert ordered_list_item_to_percentage(LEGACY_ORDERED_LIST, SPEED_LOW) == 33
    assert ordered_list_item_to_percentage(LEGACY_ORDERED_LIST, SPEED_MEDIUM) == 66
    assert ordered_list_item_to_percentage(LEGACY_ORDERED_LIST, SPEED_HIGH) == 100

    assert ordered_list_item_to_percentage(SMALL_ORDERED_LIST, SPEED_1) == 25
    assert ordered_list_item_to_percentage(SMALL_ORDERED_LIST, SPEED_2) == 50
    assert ordered_list_item_to_percentage(SMALL_ORDERED_LIST, SPEED_3) == 75
    assert ordered_list_item_to_percentage(SMALL_ORDERED_LIST, SPEED_4) == 100

    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_1) == 14
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_2) == 28
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_3) == 42
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_4) == 57
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_5) == 71
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_6) == 85
    assert ordered_list_item_to_percentage(LARGE_ORDERED_LIST, SPEED_7) == 100

    with pytest.raises(ValueError):
        assert ordered_list_item_to_percentage([], SPEED_1)


async def test_percentage_to_ordered_list_item():
    """Test item that most closely matches the percentage in an ordered list."""

    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 1) == SPEED_1
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 25) == SPEED_1
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 26) == SPEED_2
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 50) == SPEED_2
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 51) == SPEED_3
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 75) == SPEED_3
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 76) == SPEED_4
    assert percentage_to_ordered_list_item(SMALL_ORDERED_LIST, 100) == SPEED_4

    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 17) == SPEED_LOW
    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 33) == SPEED_LOW
    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 50) == SPEED_MEDIUM
    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 66) == SPEED_MEDIUM
    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 84) == SPEED_HIGH
    assert percentage_to_ordered_list_item(LEGACY_ORDERED_LIST, 100) == SPEED_HIGH

    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 1) == SPEED_1
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 14) == SPEED_1
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 25) == SPEED_2
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 26) == SPEED_2
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 28) == SPEED_2
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 29) == SPEED_3
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 41) == SPEED_3
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 42) == SPEED_3
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 43) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 56) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 50) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 51) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 75) == SPEED_6
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 76) == SPEED_6
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 100) == SPEED_7

    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 1) == SPEED_1
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 25) == SPEED_2
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 26) == SPEED_2
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 50) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 51) == SPEED_4
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 75) == SPEED_6
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 76) == SPEED_6
    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 100) == SPEED_7

    assert percentage_to_ordered_list_item(LARGE_ORDERED_LIST, 100.1) == SPEED_7

    with pytest.raises(ValueError):
        assert percentage_to_ordered_list_item([], 100)


async def test_ranged_value_to_percentage_large():
    """Test a large range of low and high values convert a single value to a percentage."""
    range = (1, 255)

    assert ranged_value_to_percentage(range, 255) == 100
    assert ranged_value_to_percentage(range, 127) == 49
    assert ranged_value_to_percentage(range, 10) == 3
    assert ranged_value_to_percentage(range, 1) == 0


async def test_percentage_to_ranged_value_large():
    """Test a large range of low and high values convert a percentage to a single value."""
    range = (1, 255)

    assert percentage_to_ranged_value(range, 100) == 255
    assert percentage_to_ranged_value(range, 50) == 127.5
    assert percentage_to_ranged_value(range, 4) == 10.2

    assert math.ceil(percentage_to_ranged_value(range, 100)) == 255
    assert math.ceil(percentage_to_ranged_value(range, 50)) == 128
    assert math.ceil(percentage_to_ranged_value(range, 4)) == 11


async def test_ranged_value_to_percentage_small():
    """Test a small range of low and high values convert a single value to a percentage."""
    range = (1, 6)

    assert ranged_value_to_percentage(range, 1) == 16
    assert ranged_value_to_percentage(range, 2) == 33
    assert ranged_value_to_percentage(range, 3) == 50
    assert ranged_value_to_percentage(range, 4) == 66
    assert ranged_value_to_percentage(range, 5) == 83
    assert ranged_value_to_percentage(range, 6) == 100


async def test_percentage_to_ranged_value_small():
    """Test a small range of low and high values convert a percentage to a single value."""
    range = (1, 6)

    assert math.ceil(percentage_to_ranged_value(range, 16)) == 1
    assert math.ceil(percentage_to_ranged_value(range, 33)) == 2
    assert math.ceil(percentage_to_ranged_value(range, 50)) == 3
    assert math.ceil(percentage_to_ranged_value(range, 66)) == 4
    assert math.ceil(percentage_to_ranged_value(range, 83)) == 5
    assert math.ceil(percentage_to_ranged_value(range, 100)) == 6
