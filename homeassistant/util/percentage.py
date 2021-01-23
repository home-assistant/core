"""Percentage util functions."""

from typing import List


def ordered_list_item_to_percentage(ordered_list: List[str], item: str) -> int:
    """Determine the percentage of an item in an ordered list.

    Given the list: ["low","medium","high","very_high"], this
    function will return the following when when the item is passed
    in:

        low: 25
        medium: 50
        high: 75
        very_high: 100

    """
    if item not in ordered_list:
        raise ValueError

    list_len = len(ordered_list)
    list_offset = ordered_list.index(item)
    return (list_offset * 100) // list_len


def percentage_to_ordered_list_item(ordered_list: List[str], percentage: int) -> str:
    """Find the item that most closely matches the percentage in an ordered list.

    Given the list: ["low","medium","high","very_high"], this
    function will return the following when when the item is passed
    in:

        1-25: low
        26-50: medium
        51-75: high
        76-100: very_high
    """
    list_len = len(ordered_list)
    if not list_len:
        raise ValueError

    for offset, speed in enumerate(ordered_list):
        upper_bound = (offset * 100) // list_len
        if percentage <= upper_bound:
            return speed

    return ordered_list[-1]


def convert_ranged_value_to_percentage(low: float, high: float, value: float) -> int:
    """Given a range of low and high values convert a single value to a percentage.

    Given a low value of 1 and a high value of 255 this function
    will return:

    255: 100
    127: 50
    10: 4
    """
    return round(value / (high - low + 1) * 100)


def convert_percentage_to_ranged_value(
    low: float, high: float, percentage: int
) -> float:
    """Given a range of low and high values convert a percentage to a single value.

    Given a low value of 1 and a high value of 255 this function
    will return:

    100: 255
    50: 127.5
    4: 10.2
    """
    return (high - low + 1) * percentage / 100
