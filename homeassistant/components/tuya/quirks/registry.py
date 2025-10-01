"""Quirks registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tuya_sharing import CustomerDevice

if TYPE_CHECKING:
    from .device_quirk import TuyaDeviceQuirk


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
