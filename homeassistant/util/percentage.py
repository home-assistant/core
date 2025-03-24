"""Percentage util functions."""

from __future__ import annotations

from .scaling import (  # noqa: F401
    int_states_in_range,
    scale_ranged_value_to_int_range,
    scale_to_ranged_value,
    states_in_range,
)


def ordered_list_item_to_percentage[_T](ordered_list: list[_T], item: _T) -> int:
    """Determine the percentage of an item in an ordered list.

    When using this utility for fan speeds, do not include "off"

    Given the list: ["low", "medium", "high", "very_high"], this
    function will return the following when the item is passed
    in:

        low: 25
        medium: 50
        high: 75
        very_high: 100

    """
    if item not in ordered_list:
        raise ValueError(f'The item "{item}" is not in "{ordered_list}"')

    list_len = len(ordered_list)
    list_position = ordered_list.index(item) + 1
    return (list_position * 100) // list_len


def percentage_to_ordered_list_item[_T](ordered_list: list[_T], percentage: int) -> _T:
    """Find the item that most closely matches the percentage in an ordered list.

    When using this utility for fan speeds, do not include "off"

    Given the list: ["low", "medium", "high", "very_high"], this
    function will return the following when when the item is passed
    in:

        1-25: low
        26-50: medium
        51-75: high
        76-100: very_high
    """
    if not (list_len := len(ordered_list)):
        raise ValueError("The ordered list is empty")

    for offset, speed in enumerate(ordered_list):
        list_position = offset + 1
        upper_bound = (list_position * 100) // list_len
        if percentage <= upper_bound:
            return speed

    return ordered_list[-1]


def ranged_value_to_percentage(
    low_high_range: tuple[float, float], value: float
) -> int:
    """Given a range of low and high values convert a single value to a percentage.

    When using this utility for fan speeds, do not include 0 if it is off

    Given a low value of 1 and a high value of 255 this function
    will return:

    (1,255), 255: 100
    (1,255), 127: 50
    (1,255), 10: 4
    """
    return scale_ranged_value_to_int_range(low_high_range, (1, 100), value)


def percentage_to_ranged_value(
    low_high_range: tuple[float, float], percentage: float
) -> float:
    """Given a range of low and high values convert a percentage to a single value.

    When using this utility for fan speeds, do not include 0 if it is off

    Given a low value of 1 and a high value of 255 this function
    will return:

    (1,255), 100: 255
    (1,255), 50: 127.5
    (1,255), 4: 10.2
    """
    return scale_to_ranged_value((1, 100), low_high_range, percentage)
