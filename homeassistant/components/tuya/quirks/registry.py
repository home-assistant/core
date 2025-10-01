"""Quirks registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

from tuya_sharing import CustomerDevice

if TYPE_CHECKING:
    from .device_quirk import TuyaDeviceQuirk

_LOGGER = logging.getLogger(__name__)


class QuirksRegistry:
    """Registry for Tuya quirks."""

    instance: Self

    _quirks: dict[str, dict[str, TuyaDeviceQuirk]]

    def __new__(cls) -> Self:
        """Create a new class."""
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        """Initialize the registry."""
        self._quirks = {}

    def register(self, category: str, product_id: str, quirk: TuyaDeviceQuirk) -> None:
        """Register a quirk for a specific device type."""
        self._quirks.setdefault(category, {})[product_id] = quirk

    def get_quirk_for_device(self, device: CustomerDevice) -> TuyaDeviceQuirk | None:
        """Get the quirk for a specific device."""
        return self._quirks.get(device.category, {}).get(device.product_id)

    def purge_custom_quirks(self, custom_quirks_root: str) -> None:
        """Purge custom quirks from the registry."""
        for category_quirks in self._quirks.values():
            to_remove = []
            for product_id, quirk in category_quirks.items():
                if quirk.quirk_file.is_relative_to(custom_quirks_root):
                    to_remove.append(product_id)

            for product_id in to_remove:
                _LOGGER.debug("Removing stale custom quirk: %s", product_id)
                category_quirks.pop(product_id)
