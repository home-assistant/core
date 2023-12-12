"""Utility to  create classes from which frozen or mutable dataclasses can be derived.

This module enabled a non-breaking transition from mutable to frozen dataclasses
derived from EntityDescription and sub classes thereof.
"""
from __future__ import annotations

import dataclasses
import sys
from typing import Any

from typing_extensions import dataclass_transform


def _class_fields(cls: type, kw_only: bool) -> list[tuple[str, Any, Any]]:
    """Return a list of dataclass fields.

    Extracted from dataclasses._process_class.
    """
    # pylint: disable=protected-access
    cls_annotations = cls.__dict__.get("__annotations__", {})

    cls_fields: list[dataclasses.Field[Any]] = []

    _dataclasses = sys.modules[dataclasses.__name__]
    for name, _type in cls_annotations.items():
        # See if this is a marker to change the value of kw_only.
        if dataclasses._is_kw_only(type, _dataclasses) or (  # type: ignore[attr-defined]
            isinstance(_type, str)
            and dataclasses._is_type(  # type: ignore[attr-defined]
                _type,
                cls,
                _dataclasses,
                dataclasses.KW_ONLY,
                dataclasses._is_kw_only,  # type: ignore[attr-defined]
            )
        ):
            kw_only = True
        else:
            # Otherwise it's a field of some type.
            cls_fields.append(dataclasses._get_field(cls, name, _type, kw_only))  # type: ignore[attr-defined]

    return [(field.name, field.type, field) for field in cls_fields]


@dataclass_transform(
    field_specifiers=(dataclasses.field, dataclasses.Field),
    kw_only_default=True,  # Set to allow setting kw_only in child classes
)
class FrozenOrThawed(type):
    """Metaclass which which makes classes which behave like a dataclass.

    This allows child classes to be either mutable or frozen dataclasses.
    """

    def _make_dataclass(cls, name: str, bases: tuple[type, ...], kw_only: bool) -> None:
        class_fields = _class_fields(cls, kw_only)
        dataclass_bases = []
        for base in bases:
            dataclass_bases.append(getattr(base, "_dataclass", base))
        cls._dataclass = dataclasses.make_dataclass(
            f"{name}_dataclass", class_fields, bases=tuple(dataclass_bases), frozen=True
        )

    def __new__(
        mcs,  # noqa: N804  ruff bug, ruff does not understand this is a metaclass
        name: str,
        bases: tuple[type, ...],
        namespace: dict[Any, Any],
        frozen_or_thawed: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Pop frozen_or_thawed and store it in the namespace."""
        namespace["_FrozenOrThawed__frozen_or_thawed"] = frozen_or_thawed
        return super().__new__(mcs, name, bases, namespace)

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[Any, Any],
        **kwargs: Any,
    ) -> None:
        """Optionally create a dataclass and store it in cls._dataclass.

        A dataclass will be created if frozen_or_thawed is set, if not we assume the
        class will be a real dataclass, i.e. it's decorated with @dataclass.
        """
        if not namespace["_FrozenOrThawed__frozen_or_thawed"]:
            parent = cls.__mro__[1]
            # This class is a real dataclass, optionally inject the parent's annotations
            if dataclasses.is_dataclass(parent) or not hasattr(parent, "_dataclass"):
                # Rely on dataclass inheritance
                return
            # Parent is not a dataclass, inject its annotations
            cls.__annotations__ = (
                parent._dataclass.__annotations__ | cls.__annotations__
            )
            return

        # First try without setting the kw_only flag, and if that fails, try setting it
        try:
            cls._make_dataclass(name, bases, False)
        except TypeError:
            cls._make_dataclass(name, bases, True)

        def __delattr__(self: object, name: str) -> None:
            """Delete an attribute.

            If self is a real dataclass, this is called if the dataclass is not frozen.
            If self is not a real dataclass, forward to cls._dataclass.__delattr.
            """
            if dataclasses.is_dataclass(self):
                return object.__delattr__(self, name)
            return self._dataclass.__delattr__(self, name)  # type: ignore[attr-defined, no-any-return]

        def __setattr__(self: object, name: str, value: Any) -> None:
            """Set an attribute.

            If self is a real dataclass, this is called if the dataclass is not frozen.
            If self is not a real dataclass, forward to cls._dataclass.__setattr__.
            """
            if dataclasses.is_dataclass(self):
                return object.__setattr__(self, name, value)
            return self._dataclass.__setattr__(self, name, value)  # type: ignore[attr-defined, no-any-return]

        # Set generated dunder methods from the dataclass
        # MyPy doesn't understand what's happening, so we ignore it
        cls.__delattr__ = __delattr__  # type: ignore[assignment, method-assign]
        cls.__eq__ = cls._dataclass.__eq__  # type: ignore[method-assign]
        cls.__init__ = cls._dataclass.__init__  # type: ignore[misc]
        cls.__repr__ = cls._dataclass.__repr__  # type: ignore[method-assign]
        cls.__setattr__ = __setattr__  # type: ignore[assignment, method-assign]
