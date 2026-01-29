"""Collection and data structure functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable, MutableSequence
import random
from typing import TYPE_CHECKING, Any

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class CollectionExtension(BaseTemplateExtension):
    """Extension for collection and data structure operations."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the collection extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "flatten",
                    self.flatten,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "shuffle",
                    self.shuffle,
                    as_global=True,
                    as_filter=True,
                ),
                # Set operations
                TemplateFunction(
                    "intersect",
                    self.intersect,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "difference",
                    self.difference,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "union",
                    self.union,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "symmetric_difference",
                    self.symmetric_difference,
                    as_global=True,
                    as_filter=True,
                ),
                # Type conversion functions
                TemplateFunction(
                    "set",
                    self.to_set,
                    as_global=True,
                ),
                TemplateFunction(
                    "tuple",
                    self.to_tuple,
                    as_global=True,
                ),
                # Type checking functions (tests)
                TemplateFunction(
                    "list",
                    self.is_list,
                    as_test=True,
                ),
                TemplateFunction(
                    "set",
                    self.is_set,
                    as_test=True,
                ),
                TemplateFunction(
                    "tuple",
                    self.is_tuple,
                    as_test=True,
                ),
            ],
        )

    def flatten(self, value: Iterable[Any], levels: int | None = None) -> list[Any]:
        """Flatten list of lists."""
        if not isinstance(value, Iterable) or isinstance(value, str):
            raise TypeError(f"flatten expected a list, got {type(value).__name__}")

        flattened: list[Any] = []
        for item in value:
            if isinstance(item, Iterable) and not isinstance(item, str):
                if levels is None:
                    flattened.extend(self.flatten(item))
                elif levels >= 1:
                    flattened.extend(self.flatten(item, levels=(levels - 1)))
                else:
                    flattened.append(item)
            else:
                flattened.append(item)
        return flattened

    def shuffle(self, *args: Any, seed: Any = None) -> MutableSequence[Any]:
        """Shuffle a list, either with a seed or without."""
        if not args:
            raise TypeError("shuffle expected at least 1 argument, got 0")

        # If first argument is iterable and more than 1 argument provided
        # but not a named seed, then use 2nd argument as seed.
        if isinstance(args[0], Iterable) and not isinstance(args[0], str):
            items = list(args[0])
            if len(args) > 1 and seed is None:
                seed = args[1]
        elif len(args) == 1:
            raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
        else:
            items = list(args)

        if seed:
            r = random.Random(seed)
            r.shuffle(items)
        else:
            random.shuffle(items)
        return items

    def intersect(self, value: Iterable[Any], other: Iterable[Any]) -> list[Any]:
        """Return the common elements between two lists."""
        if not isinstance(value, Iterable) or isinstance(value, str):
            raise TypeError(f"intersect expected a list, got {type(value).__name__}")
        if not isinstance(other, Iterable) or isinstance(other, str):
            raise TypeError(f"intersect expected a list, got {type(other).__name__}")

        return list(set(value) & set(other))

    def difference(self, value: Iterable[Any], other: Iterable[Any]) -> list[Any]:
        """Return elements in first list that are not in second list."""
        if not isinstance(value, Iterable) or isinstance(value, str):
            raise TypeError(f"difference expected a list, got {type(value).__name__}")
        if not isinstance(other, Iterable) or isinstance(other, str):
            raise TypeError(f"difference expected a list, got {type(other).__name__}")

        return list(set(value) - set(other))

    def union(self, value: Iterable[Any], other: Iterable[Any]) -> list[Any]:
        """Return all unique elements from both lists combined."""
        if not isinstance(value, Iterable) or isinstance(value, str):
            raise TypeError(f"union expected a list, got {type(value).__name__}")
        if not isinstance(other, Iterable) or isinstance(other, str):
            raise TypeError(f"union expected a list, got {type(other).__name__}")

        return list(set(value) | set(other))

    def symmetric_difference(
        self, value: Iterable[Any], other: Iterable[Any]
    ) -> list[Any]:
        """Return elements that are in either list but not in both."""
        if not isinstance(value, Iterable) or isinstance(value, str):
            raise TypeError(
                f"symmetric_difference expected a list, got {type(value).__name__}"
            )
        if not isinstance(other, Iterable) or isinstance(other, str):
            raise TypeError(
                f"symmetric_difference expected a list, got {type(other).__name__}"
            )

        return list(set(value) ^ set(other))

    def to_set(self, value: Any) -> set[Any]:
        """Convert value to set."""
        return set(value)

    def to_tuple(self, value: Any) -> tuple[Any, ...]:
        """Convert value to tuple."""
        return tuple(value)

    def is_list(self, value: Any) -> bool:
        """Return whether a value is a list."""
        return isinstance(value, list)

    def is_set(self, value: Any) -> bool:
        """Return whether a value is a set."""
        return isinstance(value, set)

    def is_tuple(self, value: Any) -> bool:
        """Return whether a value is a tuple."""
        return isinstance(value, tuple)
