"""The unifiprotect integration models."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pyunifiprotect.data import NVR, Event, ProtectAdoptableDeviceModel

from homeassistant.helpers.entity import EntityDescription

from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ProtectAdoptableDeviceModel | NVR)


def split_tuple(value: tuple[str, ...] | str | None) -> tuple[str, ...] | None:
    """Split string to tuple."""
    if value is None:
        return None
    if TYPE_CHECKING:
        assert isinstance(value, str)
    return tuple(value.split("."))


class PermRequired(int, Enum):
    """Type of permission level required for entity."""

    NO_WRITE = 1
    WRITE = 2
    DELETE = 3


@dataclass(frozen=True, kw_only=True)
class ProtectRequiredKeysMixin(EntityDescription, Generic[T]):
    """Mixin for required keys."""

    # `ufp_required_field`, `ufp_value`, and `ufp_enabled` are defined as
    # a `str` in the dataclass, but `__post_init__` converts it to a
    # `tuple[str, ...]` to avoid doing it at run time in `get_nested_attr`
    # which is usually called millions of times per day.
    ufp_required_field: tuple[str, ...] | str | None = None
    ufp_value: tuple[str, ...] | str | None = None
    ufp_value_fn: Callable[[T], Any] | None = None
    ufp_enabled: tuple[str, ...] | str | None = None
    ufp_perm: PermRequired | None = None

    def __post_init__(self) -> None:
        """Pre-convert strings to tuples for faster get_nested_attr."""
        object.__setattr__(
            self, "ufp_required_field", split_tuple(self.ufp_required_field)
        )
        object.__setattr__(self, "ufp_value", split_tuple(self.ufp_value))
        object.__setattr__(self, "ufp_enabled", split_tuple(self.ufp_enabled))

    def get_ufp_value(self, obj: T) -> Any:
        """Return value from UniFi Protect device."""
        if (ufp_value := self.ufp_value) is not None:
            if TYPE_CHECKING:
                # `ufp_value` is defined as a `str` in the dataclass, but
                # `__post_init__` converts it to a `tuple[str, ...]` to avoid
                # doing it at run time in `get_nested_attr` which is usually called
                # millions of times per day. This tells mypy that it's a tuple.
                assert isinstance(ufp_value, tuple)
            return get_nested_attr(obj, ufp_value)
        if (ufp_value_fn := self.ufp_value_fn) is not None:
            return ufp_value_fn(obj)

        # reminder for future that one is required
        raise RuntimeError(  # pragma: no cover
            "`ufp_value` or `ufp_value_fn` is required"
        )

    def get_ufp_enabled(self, obj: T) -> bool:
        """Return value from UniFi Protect device."""
        if (ufp_enabled := self.ufp_enabled) is not None:
            if TYPE_CHECKING:
                # `ufp_enabled` is defined as a `str` in the dataclass, but
                # `__post_init__` converts it to a `tuple[str, ...]` to avoid
                # doing it at run time in `get_nested_attr` which is usually called
                # millions of times per day. This tells mypy that it's a tuple.
                assert isinstance(ufp_enabled, tuple)
            return bool(get_nested_attr(obj, ufp_enabled))
        return True

    def has_required(self, obj: T) -> bool:
        """Return if has required field."""
        if (ufp_required_field := self.ufp_required_field) is None:
            return True
        if TYPE_CHECKING:
            # `ufp_required_field` is defined as a `str` in the dataclass, but
            # `__post_init__` converts it to a `tuple[str, ...]` to avoid
            # doing it at run time in `get_nested_attr` which is usually called
            # millions of times per day. This tells mypy that it's a tuple.
            assert isinstance(ufp_required_field, tuple)
        return bool(get_nested_attr(obj, ufp_required_field))


@dataclass(frozen=True, kw_only=True)
class ProtectEventMixin(ProtectRequiredKeysMixin[T]):
    """Mixin for events."""

    ufp_event_obj: str | None = None

    def get_event_obj(self, obj: T) -> Event | None:
        """Return value from UniFi Protect device."""

        if self.ufp_event_obj is not None:
            event: Event | None = getattr(obj, self.ufp_event_obj, None)
            return event
        return None

    def get_is_on(self, obj: T, event: Event | None) -> bool:
        """Return value if event is active."""

        return event is not None and self.get_ufp_value(obj)


@dataclass(frozen=True, kw_only=True)
class ProtectSetableKeysMixin(ProtectRequiredKeysMixin[T]):
    """Mixin for settable values."""

    ufp_set_method: str | None = None
    ufp_set_method_fn: Callable[[T, Any], Coroutine[Any, Any, None]] | None = None

    async def ufp_set(self, obj: T, value: Any) -> None:
        """Set value for UniFi Protect device."""
        _LOGGER.debug("Setting %s to %s for %s", self.name, value, obj.display_name)
        if self.ufp_set_method is not None:
            await getattr(obj, self.ufp_set_method)(value)
        elif self.ufp_set_method_fn is not None:
            await self.ufp_set_method_fn(obj, value)
