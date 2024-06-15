"""The unifiprotect integration models."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from uiprotect.data import NVR, Event, ProtectAdoptableDeviceModel

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
class ProtectEntityDescription(EntityDescription, Generic[T]):
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

    def get_ufp_value(self, obj: T) -> Any:
        """Return value from UniFi Protect device."""
        raise RuntimeError(
            "`ufp_value` or `ufp_value_fn` is required"
        )  # pragma: no cover

    def has_required(self, obj: T) -> bool:
        """Return if required field is set."""
        return True

    def get_ufp_enabled(self, obj: T) -> bool:
        """Return if entity is enabled."""
        return True

    def __post_init__(self) -> None:
        """Pre-convert strings to tuples for faster get_nested_attr."""
        _setter = partial(object.__setattr__, self)
        if (_ufp_value := self.ufp_value) is not None:
            ufp_value = split_tuple(_ufp_value)
            assert isinstance(ufp_value, tuple)
            _setter("get_ufp_value", partial(get_nested_attr, attrs=ufp_value))
        elif (ufp_value_fn := self.ufp_value_fn) is not None:
            _setter("get_ufp_value", ufp_value_fn)

        if (_ufp_enabled := self.ufp_enabled) is not None:
            ufp_enabled = split_tuple(_ufp_enabled)
            assert isinstance(ufp_enabled, tuple)
            _setter("get_ufp_enabled", partial(get_nested_attr, attrs=ufp_enabled))

        if (_ufp_required_field := self.ufp_required_field) is not None:
            ufp_required_field = split_tuple(_ufp_required_field)
            assert isinstance(ufp_required_field, tuple)
            _setter(
                "has_required",
                lambda obj: bool(get_nested_attr(obj, ufp_required_field)),
            )


@dataclass(frozen=True, kw_only=True)
class ProtectEventMixin(ProtectEntityDescription[T]):
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
class ProtectSetableKeysMixin(ProtectEntityDescription[T]):
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
