"""Utils for NextBus integration module."""

from typing import Any


def listify(maybe_list: Any) -> list[Any]:
    """Return list version of whatever value is passed in.

    This is used to provide a consistent way of interacting with the JSON
    results from the API. There are several attributes that will either missing
    if there are no values, a single dictionary if there is only one value, and
    a list if there are multiple.
    """
    if maybe_list is None:
        return []
    if isinstance(maybe_list, list):
        return maybe_list
    return [maybe_list]


def maybe_first(maybe_list: list[Any] | None) -> Any:
    """Return the first item out of a list or returns back the input."""
    if isinstance(maybe_list, list) and maybe_list:
        return maybe_list[0]

    return maybe_list
