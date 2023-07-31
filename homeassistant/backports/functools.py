"""Functools backports from standard lib."""
from __future__ import annotations

from collections.abc import Callable
from types import GenericAlias
from typing import Any, Generic, Self, TypeVar, overload

_T = TypeVar("_T")


class cached_property(Generic[_T]):  # pylint: disable=invalid-name
    """Backport of Python 3.12's cached_property.

    Includes https://github.com/python/cpython/pull/101890/files
    """

    def __init__(self, func: Callable[[Any], _T]) -> None:
        """Initialize."""
        self.func: Callable[[Any], _T] = func
        self.attrname: str | None = None
        self.__doc__ = func.__doc__

    def __set_name__(self, owner: type[Any], name: str) -> None:
        """Set name."""
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    @overload
    def __get__(self, instance: None, owner: type[Any] | None = None) -> Self:
        ...

    @overload
    def __get__(self, instance: Any, owner: type[Any] | None = None) -> _T:
        ...

    def __get__(
        self, instance: Any | None, owner: type[Any] | None = None
    ) -> _T | Self:
        """Get."""
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it."
            )
        try:
            cache = instance.__dict__
        # not all objects have __dict__ (e.g. class defines slots)
        except AttributeError:
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        val = self.func(instance)
        try:
            cache[self.attrname] = val
        except TypeError:
            msg = (
                f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                f"does not support item assignment for caching {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        return val

    __class_getitem__ = classmethod(GenericAlias)
