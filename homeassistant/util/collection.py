"""Helpers for working with collections."""

from collections.abc import Collection, Iterable
from functools import partial
from itertools import islice
from typing import Any


def take(take_num: int, iterable: Iterable) -> list[Any]:
    """Return first n items of the iterable as a list.

    From itertools recipes
    """
    return list(islice(iterable, take_num))


def chunked(iterable: Iterable, chunked_num: int) -> Iterable[Any]:
    """Break *iterable* into lists of length *n*.

    From more-itertools
    """
    return iter(partial(take, chunked_num, iter(iterable)), [])


def chunked_or_all(iterable: Collection[Any], chunked_num: int) -> Iterable[Any]:
    """Break *collection* into iterables of length *n*.

    Returns the collection if its length is less than *n*.

    Unlike chunked, this function requires a collection so it can
    determine the length of the collection and return the collection
    if it is less than *n*.
    """
    if len(iterable) <= chunked_num:
        return (iterable,)
    return chunked(iterable, chunked_num)
