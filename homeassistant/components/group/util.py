"""Utility functions to combine state attributes from multiple entities."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from itertools import groupby
from typing import Any

from homeassistant.core import State


def find_state_attributes(states: list[State], key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        if (value := state.attributes.get(key)) is not None:
            yield value


def find_state(states: list[State]) -> Iterator[Any]:
    """Find state from states."""
    for state in states:
        yield state.state


def mean_int(*args: Any) -> int:
    """Return the mean of the supplied values."""
    return int(sum(args) / len(args))


def mean_tuple(*args: Any) -> tuple[float | Any, ...]:
    """Return the mean values along the columns of the supplied values."""
    return tuple(sum(x) / len(x) for x in zip(*args))


def attribute_equal(states: list[State], key: str) -> bool:
    """Return True if all attributes found matching key from states are equal.

    Note: Returns True if no matching attribute is found.
    """
    return _values_equal(find_state_attributes(states, key))


def most_frequent_attribute(states: list[State], key: str) -> Any | None:
    """Find attributes with matching key from states."""
    if attrs := list(find_state_attributes(states, key)):
        return max(set(attrs), key=attrs.count)
    return None


def states_equal(states: list[State]) -> bool:
    """Return True if all states are equal.

    Note: Returns True if no matching attribute is found.
    """
    return _values_equal(find_state(states))


def _values_equal(values: Iterator[Any]) -> bool:
    """Return True if all values are equal.

    Note: Returns True if no matching attribute is found.
    """
    grp = groupby(values)
    return bool(next(grp, True) and not next(grp, False))


def reduce_attribute(
    states: list[State],
    key: str,
    default: Any | None = None,
    reduce: Callable[..., Any] = mean_int,
) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)
