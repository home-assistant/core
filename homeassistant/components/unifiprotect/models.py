"""The unifiprotect integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Generic, TypeVar, cast

from pyunifiprotect.data import NVR, Event, ProtectAdoptableDeviceModel

from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import dt as dt_util

from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ProtectAdoptableDeviceModel | NVR)


class PermRequired(int, Enum):
    """Type of permission level required for entity."""

    NO_WRITE = 1
    WRITE = 2
    DELETE = 3


@dataclass
class ProtectRequiredKeysMixin(EntityDescription, Generic[T]):
    """Mixin for required keys."""

    ufp_required_field: str | None = None
    ufp_value: str | None = None
    ufp_value_fn: Callable[[T], Any] | None = None
    ufp_enabled: str | None = None
    ufp_perm: PermRequired | None = None

    def get_ufp_value(self, obj: T) -> Any:
        """Return value from UniFi Protect device."""
        if self.ufp_value is not None:
            return get_nested_attr(obj, self.ufp_value)
        if self.ufp_value_fn is not None:
            return self.ufp_value_fn(obj)

        # reminder for future that one is required
        raise RuntimeError(  # pragma: no cover
            "`ufp_value` or `ufp_value_fn` is required"
        )

    def get_ufp_enabled(self, obj: T) -> bool:
        """Return value from UniFi Protect device."""
        if self.ufp_enabled is not None:
            return bool(get_nested_attr(obj, self.ufp_enabled))
        return True

    def has_required(self, obj: T) -> bool:
        """Return if has required field."""

        if self.ufp_required_field is None:
            return True
        return bool(get_nested_attr(obj, self.ufp_required_field))


@dataclass
class ProtectEventMixin(ProtectRequiredKeysMixin[T]):
    """Mixin for events."""

    ufp_event_obj: str | None = None

    def get_event_obj(self, obj: T) -> Event | None:
        """Return value from UniFi Protect device."""

        if self.ufp_event_obj is not None:
            return cast(Event, get_nested_attr(obj, self.ufp_event_obj))
        return None

    def get_is_on(self, event: Event | None) -> bool:
        """Return value if event is active."""
        if event is None:
            return False

        now = dt_util.utcnow()
        value = now > event.start
        if value and event.end is not None and now > event.end:
            value = False

        return value


@dataclass
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
