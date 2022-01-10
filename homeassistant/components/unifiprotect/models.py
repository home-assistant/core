"""The unifiprotect integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pyunifiprotect.data import NVR, ProtectAdoptableDeviceModel

from homeassistant.helpers.entity import EntityDescription

from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectRequiredKeysMixin:
    """Mixin for required keys."""

    ufp_required_field: str | None = None
    ufp_value: str | None = None
    ufp_value_fn: Callable[[ProtectAdoptableDeviceModel | NVR], Any] | None = None

    def get_ufp_value(self, obj: ProtectAdoptableDeviceModel | NVR) -> Any:
        """Return value from UniFi Protect device."""
        if self.ufp_value is not None:
            return get_nested_attr(obj, self.ufp_value)
        if self.ufp_value_fn is not None:
            return self.ufp_value_fn(obj)

        # reminder for future that one is required
        raise RuntimeError(  # pragma: no cover
            "`ufp_value` or `ufp_value_fn` is required"
        )


@dataclass
class ProtectSetableKeysMixin(ProtectRequiredKeysMixin):
    """Mixin to for settable values."""

    ufp_set_method: str | None = None
    ufp_set_method_fn: Callable[
        [ProtectAdoptableDeviceModel, Any], Coroutine[Any, Any, None]
    ] | None = None

    async def ufp_set(self, obj: ProtectAdoptableDeviceModel, value: Any) -> None:
        """Set value for UniFi Protect device."""
        assert isinstance(self, EntityDescription)
        _LOGGER.debug("Setting %s to %s for %s", self.name, value, obj.name)
        if self.ufp_set_method is not None:
            await getattr(obj, self.ufp_set_method)(value)
        elif self.ufp_set_method_fn is not None:
            await self.ufp_set_method_fn(obj, value)
