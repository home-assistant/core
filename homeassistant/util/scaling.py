"""Scaling util functions."""

from __future__ import annotations


def scale_ranged_value_to_int_range(
    source_low_high_range: tuple[float, float],
    target_low_high_range: tuple[float, float],
    value: float,
) -> int:
    """Given a range of low and high values convert a single value to another range.

    Given a source low value of 1 and a high value of 255 and
    a target range from 1 to 100 this function
    will return:

    (1,255), (1,100), 255: 100
    (1,255), (1,100), 127: 49
    (1,255), (1,100), 10: 3
    """
    source_offset = source_low_high_range[0] - 1
    target_offset = target_low_high_range[0] - 1
    return int(
        (value - source_offset)
        * states_in_range(target_low_high_range)
        // states_in_range(source_low_high_range)
        + target_offset
    )


def scale_to_ranged_value(
    source_low_high_range: tuple[float, float],
    target_low_high_range: tuple[float, float],
    value: float,
) -> float:
    """Given a range of low and high values convert a single value to another range.

    Do not include 0 in a range if 0 means off,
    e.g. for brightness or fan speed.

    Given a source low value of 1 and a high value of 255 and
    a target range from 1 to 100 this function
    will return:

    (1,255), 255: 100
    (1,255), 127: ~49.8039
    (1,255), 10: ~3.9216
    """
    source_offset = source_low_high_range[0] - 1
    target_offset = target_low_high_range[0] - 1
    return (value - source_offset) * (
        states_in_range(target_low_high_range)
    ) / states_in_range(source_low_high_range) + target_offset


def states_in_range(low_high_range: tuple[float, float]) -> float:
    """Given a range of low and high values return how many states exist."""
    return low_high_range[1] - low_high_range[0] + 1


def int_states_in_range(low_high_range: tuple[float, float]) -> int:
    """Given a range of low and high values return how many integer states exist."""
    return int(states_in_range(low_high_range))
