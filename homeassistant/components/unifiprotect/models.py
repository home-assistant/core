"""The unifiprotect integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Generic, TypeVar

from pyunifiprotect.data import ProtectDeviceModel

from homeassistant.helpers.entity import EntityDescription

from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ProtectDeviceModel)


@dataclass
class ProtectRequiredKeysMixin(Generic[T]):
    """Mixin for required keys."""

    ufp_required_field: str | None = None
    ufp_value: str | None = None
    ufp_value_fn: Callable[[T], Any] | None = None
    ufp_enabled: str | None = None

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


@dataclass
class ProtectSetableKeysMixin(ProtectRequiredKeysMixin, Generic[T]):
    """Mixin for settable values."""

    ufp_set_method: str | None = None
    ufp_set_method_fn: Callable[[T, Any], Coroutine[Any, Any, None]] | None = None

    async def ufp_set(self, obj: T, value: Any) -> None:
        """Set value for UniFi Protect device."""
        assert isinstance(self, EntityDescription)
        _LOGGER.debug("Setting %s to %s for %s", self.name, value, obj.name)
        if self.ufp_set_method is not None:
            await getattr(obj, self.ufp_set_method)(value)
        elif self.ufp_set_method_fn is not None:
            await self.ufp_set_method_fn(obj, value)
