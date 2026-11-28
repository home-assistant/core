"""Describe values for the Debug console, and inspect them on request."""

import builtins
from collections.abc import (
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Set as AbstractSet,
    Sized,
)
from contextlib import suppress
from dataclasses import dataclass
from itertools import islice
import reprlib
import traceback
from types import GetSetDescriptorType, MemberDescriptorType
from typing import TYPE_CHECKING, Any, TypeGuard, override

if TYPE_CHECKING:
    from .session import ConsoleSession

# What code of the user can raise, which must not stop Home Assistant or close
# the connection: anything, as code can raise BaseException itself. That
# includes CancelledError, like a property reading a cancelled future;
# executions tell a real cancellation apart.
USER_CODE_ERRORS = (BaseException,)

# How Python itself reads a class, past any __getattribute__ of its metaclass,
# which is code of the user.
_CLASS_MRO = vars(type)["__mro__"]
_CLASS_DICT = vars(type)["__dict__"]
_CLASS_QUALNAME = vars(type)["__qualname__"]

MAX_CHILDREN = 1000
MAX_STRING_LENGTH = 10000

# Marks a property among children, which is only evaluated on request.
_GETTER = object()

_NOT_FOUND = object()


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

    def repr_bytes(self, x: bytes, level: int) -> str:
        """Represent only the start, instead of all of it before cutting it."""
        return self._repr_start(x, builtins.repr(x[: self.maxstring]))

    def repr_bytearray(self, x: bytearray, level: int) -> str:
        """Represent only the start, instead of all of it before cutting it."""
        return self._repr_start(x, builtins.repr(x[: self.maxstring]))

    def _repr_start(self, x: bytes | bytearray, start: str) -> str:
        if len(x) <= self.maxstring:
            return start

        return f"{start[:-1]}{self.fillvalue}{start[-1]}"

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
    # Exact types only: subclasses can bring their own __repr__ and friends,
    # which then show like any other object.

    if type(value) is bool:
        return {"type": "boolean", "value": value}

    if has_type(value, (int, float)):
        # As a string, as JSON cannot hold big integers, infinity or NaN.
        return {"type": "number", "value": repr(value)}

    if type(value) is str:
        return {
            "type": "string",
            "value": value[:MAX_STRING_LENGTH],
            "truncated": len(value) > MAX_STRING_LENGTH,
        }

    description: dict[str, Any] = {
        "type": "object",
        "class": class_name(value),
        "preview": preview(value),
        "object_id": session.track(value),
    }
    if isinstance(value, Sized):
        with suppress(*USER_CODE_ERRORS):
            description["length"] = len(value)

    return description


def preview(value: Any) -> str:
    """Return a short representation, also of objects with a broken __repr__."""
    try:
        return _PREVIEW.repr(value)
    except USER_CODE_ERRORS:
        return f"<{class_name(value)} that failed to represent itself>"


def inspect_children(session: ConsoleSession, value: Any) -> dict[str, Any]:
    """Describe the children of a value, such as its items or attributes.

    Iterating containers runs their code, so this raises what that raises.
    """
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
        return {"value": describe(session, getattr(value, name))}
    except USER_CODE_ERRORS as err:
        return {"error": format_error(err)}


def has_type(value: Any, types: Iterable[type]) -> bool:
    """Return if the type of a value is exactly one of these, without running code.

    Unlike a type in a tuple, which compares with ==, and a metaclass can
    change what that does.
    """
    return any(type(value) is allowed for allowed in types)


def is_class(value: Any) -> TypeGuard[type]:
    """Return if a value is a class, without running code.

    Unlike isinstance(), which reads __class__, and that can be a property.
    """
    return issubclass(type(value), type)


def format_error(err: BaseException) -> str:
    """Format an exception in a line, like Python does after its traceback.

    That runs code of the exception, like its __notes__, which can raise too.
    """
    try:
        return "".join(traceback.format_exception_only(err)).strip()
    except USER_CODE_ERRORS:
        return f"<{class_name(err)} that failed to format>"


def class_mro(cls: type) -> tuple[type, ...]:
    """Return a class and the classes it inherits from, without running code."""
    return _CLASS_MRO.__get__(cls)  # type: ignore[no-any-return]  # pylint: disable=unnecessary-dunder-call


def class_dict(cls: type) -> dict[str, Any]:
    """Return the attributes a class defines itself, without running code."""
    return with_string_names(_CLASS_DICT.__get__(cls).items())  # pylint: disable=unnecessary-dunder-call


def with_string_names(items: Iterable[tuple[Any, Any]]) -> dict[str, Any]:
    """Return names and their values, keeping only names that are a str.

    A name can be a subclass of str, whose own __hash__, __eq__, and other
    methods would run when comparing or matching it. Copied in one go first,
    as other threads can change a dictionary, like sys.modules, meanwhile.
    """
    return {name: value for name, value in list(items) if type(name) is str}


def class_name(value: Any) -> str:
    """Return the name of the class of a value, without running code.

    As a str itself: a class can name itself with a subclass of str, whose own
    __str__ and __format__ would run when the name is logged or formatted.
    """
    return str.__str__(_CLASS_QUALNAME.__get__(type(value)))  # pylint: disable=unnecessary-dunder-call


def static_attribute(value: Any, name: str, default: Any = None) -> Any:
    """Return an attribute as stored, without running any code to get it.

    Like inspect.getattr_static, which still goes through a __getattribute__
    of the metaclass when looking at classes.
    """
    if (found := static_lookup(value, name)) is None:
        return default

    return found.attribute


@dataclass(slots=True, frozen=True)
class StaticLookup:
    """An attribute as stored, and what getattr() would bind it to.

    Without an owner, the attribute is stored on the instance itself, and
    getattr() returns it as is. Otherwise its __get__ gets the instance, which
    is None for an attribute of a class, and the owner.
    """

    attribute: Any
    instance: Any = None
    owner: type | None = None


def static_lookup(value: Any, name: str) -> StaticLookup | None:
    """Look up an attribute like getattr(), without running any code.

    Data descriptors of the class win over the instance, and attributes of a
    metaclass apply to its classes, like they do for getattr.
    """
    if is_class(value):
        found = _class_attribute(value, name, _NOT_FOUND)
        from_metaclass = _class_attribute(type(value), name, _NOT_FOUND)
        if from_metaclass is not _NOT_FOUND and (
            found is _NOT_FOUND or _is_data_descriptor(from_metaclass)
        ):
            return StaticLookup(from_metaclass, value, type(value))

        if found is _NOT_FOUND:
            return None

        return StaticLookup(found, None, value)

    from_class = _class_attribute(type(value), name, _NOT_FOUND)
    if from_class is not _NOT_FOUND and _is_data_descriptor(from_class):
        return StaticLookup(from_class, value, type(value))

    if (attributes := instance_dict(value)) is not None and name in attributes:
        return StaticLookup(attributes[name])

    if from_class is _NOT_FOUND:
        return None

    return StaticLookup(from_class, value, type(value))


def _class_attribute(cls: type, name: str, default: Any) -> Any:
    """Return an attribute a class defines or inherits, as stored."""
    for base in class_mro(cls):
        if name in (attributes := class_dict(base)):
            return attributes[name]

    return default


def is_descriptor(value: Any) -> bool:
    """Return if a value is a descriptor, without running code."""
    return any("__get__" in class_dict(base) for base in class_mro(type(value)))


def _is_data_descriptor(value: Any) -> bool:
    """Return if a value is a descriptor that can be set, like a property."""
    return any(
        "__set__" in class_dict(base) or "__delete__" in class_dict(base)
        for base in class_mro(type(value))
    )


def instance_dict(value: Any) -> dict[str, Any] | None:
    """Return the __dict__ of an instance, without running code to get it.

    A class can replace __dict__ with a property, which is then left alone.
    """
    # A class keeps its attributes behind a read only view.
    if is_class(value):
        return class_dict(value)

    # Only the class of the instance counts, not the class of that class.
    for cls in class_mro(type(value)):
        if "__dict__" in (attributes := class_dict(cls)):
            descriptor = attributes["__dict__"]
            break
    else:
        return None

    if not has_type(descriptor, (GetSetDescriptorType, MemberDescriptorType)):
        return None

    # Code can set a subclass of dict, with methods of its own. Its items view
    # reads the dict underneath.
    attributes = descriptor.__get__(value, type(value))  # pylint: disable=unnecessary-dunder-call
    return with_string_names(dict.items(attributes))


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

    # A data descriptor of the class wins over the instance, like for getattr.
    attributes: dict[str, Any] = {
        name: item
        for name, item in (instance_dict(value) or {}).items()
        if not _is_data_descriptor(_class_attribute(type(value), name, None))
    }

    for cls in class_mro(type(value)):
        slots = class_dict(cls).get("__slots__", ())
        for name in (slots,) if isinstance(slots, str) else slots:
            # A subclass can replace a slot with a property, which only runs
            # on request; the loop below marks it.
            static = static_attribute(type(value), name)
            if isinstance(static, MemberDescriptorType):
                with suppress(AttributeError):
                    attributes[name] = static.__get__(value, type(value))  # pylint: disable=unnecessary-dunder-call

    for name in {name for cls in class_mro(type(value)) for name in class_dict(cls)}:
        if name in attributes:
            continue

        static = static_attribute(type(value), name)
        # Matched by name, as both functools and propcache have their own.
        if _is_data_descriptor(static) or class_name(static) == "cached_property":
            attributes[name] = _GETTER

    for name in sorted(attributes):
        if not name.startswith("__"):
            yield name, attributes[name]
