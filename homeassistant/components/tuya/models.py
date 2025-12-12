"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

from typing import Self

from tuya_device_handlers.device_wrapper import DPCodeWrapper
from tuya_device_handlers.type_information import BitmapTypeInformation
from tuya_sharing import CustomerDevice


class DPCodeBitmapBitWrapper(DPCodeWrapper):
    """Simple wrapper for a specific bit in bitmap values."""

    def __init__(self, dpcode: str, mask: int) -> None:
        """Init DPCodeBitmapWrapper."""
        super().__init__(dpcode)
        self._mask = mask

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        return (raw_value & (1 << self._mask)) != 0

    @classmethod
    def find_dpcode(
        cls,
        device: CustomerDevice,
        dpcodes: str | tuple[str, ...],
        *,
        bitmap_key: str,
    ) -> Self | None:
        """Find and return a DPCodeBitmapBitWrapper for the given DP codes."""
        if (
            type_information := BitmapTypeInformation.find_dpcode(device, dpcodes)
        ) and bitmap_key in type_information.label:
            return cls(
                type_information.dpcode, type_information.label.index(bitmap_key)
            )
        return None
