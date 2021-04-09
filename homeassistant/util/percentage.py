"""Percentage util functions."""
from __future__ import annotations


def ordered_list_item_to_percentage(ordered_list: list[str], item: str) -> int:
    """Determine the percentage of an item in an ordered list.

    When using this utility for fan speeds, do not include "off"

    Given the list: ["low", "medium", "high", "very_high"], this
    function will return the following when when the item is passed
    in:

        low: 25
        medium: 50
        high: 75
        very_high: 100

    """
    if item not in ordered_list:
        raise ValueError(f'The item "{item}"" is not in "{ordered_list}"')

    list_len = len(ordered_list)
    list_position = ordered_list.index(item) + 1
    return (list_position * 100) // list_len


def percentage_to_ordered_list_item(ordered_list: list[str], percentage: int) -> str:
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
    list_len = len(ordered_list)
    if not list_len:
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
    offset = low_high_range[0] - 1
    return int(((value - offset) * 100) // states_in_range(low_high_range))


def percentage_to_ranged_value(
    low_high_range: tuple[float, float], percentage: int
) -> float:
    """Given a range of low and high values convert a percentage to a single value.

    When using this utility for fan speeds, do not include 0 if it is off

    Given a low value of 1 and a high value of 255 this function
    will return:

    (1,255), 100: 255
    (1,255), 50: 127.5
    (1,255), 4: 10.2
    """
    offset = low_high_range[0] - 1
    return states_in_range(low_high_range) * percentage / 100 + offset


def states_in_range(low_high_range: tuple[float, float]) -> float:
    """Given a range of low and high values return how many states exist."""
    return low_high_range[1] - low_high_range[0] + 1


def int_states_in_range(low_high_range: tuple[float, float]) -> int:
    """Given a range of low and high values return how many integer states exist."""
    return int(states_in_range(low_high_range))
