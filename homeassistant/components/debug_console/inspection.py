"""Describe values for the Debug console, and inspect them on request."""

from collections.abc import Iterator, Mapping, Sequence, Set as AbstractSet, Sized
from contextlib import suppress
import inspect
from itertools import islice
import reprlib
import traceback
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from .session import ConsoleSession

MAX_CHILDREN = 1000
MAX_STRING_LENGTH = 10000

# Marks a property among children, which is only evaluated on request.
_GETTER = object()


class _PreviewRepr(reprlib.Repr):
    """Short representations, in iteration order.

    The standard implementation sorts dictionaries and sets completely before
    showing a handful of items, which is slow for large containers.
    """

    @override
    def repr_dict(self, x: dict[Any, Any], level: int) -> str:
        if not x:
            return "{}"
        if level <= 0:
            return f"{{{self.fillvalue}}}"
        pieces = [
            f"{self.repr1(key, level - 1)}: {self.repr1(value, level - 1)}"
            for key, value in islice(x.items(), self.maxdict)
        ]
        return f"{{{self._join_pieces(pieces, len(x) > self.maxdict)}}}"

    @override
    def repr_set(self, x: set[Any], level: int) -> str:
        if not x:
            return "set()"
        return f"{{{self._repr_items(x, level, self.maxset)}}}"

    @override
    def repr_frozenset(self, x: frozenset[Any], level: int) -> str:
        if not x:
            return "frozenset()"
        return f"frozenset({{{self._repr_items(x, level, self.maxfrozenset)}}})"

    def _repr_items(self, x: AbstractSet[Any], level: int, maximum: int) -> str:
        if level <= 0:
            return self.fillvalue
        pieces = [self.repr1(item, level - 1) for item in islice(x, maximum)]
        return self._join_pieces(pieces, len(x) > maximum)

    def _join_pieces(self, pieces: list[str], truncated: bool) -> str:
        return ", ".join([*pieces, self.fillvalue] if truncated else pieces)


_PREVIEW = _PreviewRepr(
    maxlevel=2,
    maxtuple=5,
    maxlist=5,
    maxdict=5,
    maxset=5,
    maxfrozenset=5,
    maxdeque=5,
    maxstring=80,
    maxlong=40,
    maxother=80,
)


def describe(session: ConsoleSession, value: Any) -> dict[str, Any]:
    """Describe a value for the frontend, tracking objects so they can expand."""
    if value is None:
        return {"type": "none"}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, int | float):
        # As a string, as JSON cannot hold big integers, infinity or NaN.
        return {"type": "number", "value": repr(value)}
    if isinstance(value, str):
        return {
            "type": "string",
            "value": value[:MAX_STRING_LENGTH],
            "truncated": len(value) > MAX_STRING_LENGTH,
        }

    description: dict[str, Any] = {
        "type": "object",
        "class": type(value).__qualname__,
        "preview": preview(value),
        "object_id": session.track(value),
    }
    if isinstance(value, Sized):
        with suppress(Exception):
            description["length"] = len(value)
    return description


def preview(value: Any) -> str:
    """Return a short representation, surviving objects with a broken repr."""
    try:
        return _PREVIEW.repr(value)
    except Exception as err:  # noqa: BLE001
        return f"<repr() failed: {err!r}>"


def inspect_children(session: ConsoleSession, value: Any) -> dict[str, Any]:
    """Describe the children of a value, such as its items or attributes."""
    children: list[dict[str, Any]] = []
    for key, child in islice(_iter_children(value), MAX_CHILDREN + 1):
        if child is _GETTER:
            children.append({"key": key, "getter": True})
        else:
            children.append({"key": key, "value": describe(session, child)})

    return {
        "children": children[:MAX_CHILDREN],
        "truncated": len(children) > MAX_CHILDREN,
    }


def get_attribute(session: ConsoleSession, value: Any, name: str) -> dict[str, Any]:
    """Evaluate an attribute, such as a property the user asked for."""
    try:
        attribute = getattr(value, name)
    except Exception as err:  # noqa: BLE001
        return {"error": "".join(traceback.format_exception_only(err))}

    return {"value": describe(session, attribute)}


def _iter_children(value: Any) -> Iterator[tuple[str, Any]]:
    """Yield the children of a value as key and value pairs.

    Properties yield a marker instead of their value, as evaluating them can
    have side effects. The frontend evaluates them on request.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield preview(key), item
        return

    if isinstance(value, Sequence | AbstractSet) and not isinstance(
        value, str | bytes | bytearray
    ):
        for index, item in enumerate(value):
            yield str(index), item
        return

    attributes: dict[str, Any] = {}
    with suppress(TypeError):
        attributes.update(vars(value))

    for cls in type(value).__mro__:
        slots = getattr(cls, "__slots__", ())
        for name in (slots,) if isinstance(slots, str) else slots:
            try:
                attributes[name] = getattr(value, name)
            except AttributeError:
                continue

    for name in dir(type(value)):
        if name in attributes:
            continue
        static = inspect.getattr_static(type(value), name, None)
        # Matched by name, as both functools and propcache have their own.
        if inspect.isdatadescriptor(static) or (
            type(static).__name__ == "cached_property"
        ):
            attributes[name] = _GETTER

    for name in sorted(attributes):
        if not name.startswith("__"):
            yield name, attributes[name]
