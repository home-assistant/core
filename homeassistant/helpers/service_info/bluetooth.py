"""The bluetooth integration service info."""
from __future__ import annotations

import dataclasses
from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import BaseServiceInfo

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData


@dataclasses.dataclass
class BluetoothServiceInfo(BaseServiceInfo):
    """Prepared info from bluetooth entries."""

    name: str
    address: str
    rssi: int
    manufacturer_data: dict[int, bytes]
    service_data: dict[str, bytes]
    service_uuids: list[str]
    source: str

    @classmethod
    def from_advertisement(
        cls, device: BLEDevice, advertisement_data: AdvertisementData, source: str
    ) -> BluetoothServiceInfo:
        """Create a BluetoothServiceInfo from an advertisement."""
        return cls(
            name=advertisement_data.local_name or device.name or device.address,
            address=device.address,
            rssi=device.rssi,
            manufacturer_data=advertisement_data.manufacturer_data,
            service_data=advertisement_data.service_data,
            service_uuids=advertisement_data.service_uuids,
            source=source,
        )

    @cached_property
    def manufacturer(self) -> str | None:
        """Convert manufacturer data to a string."""
        from bleak.backends.device import (  # pylint: disable=import-outside-toplevel
            MANUFACTURERS,
        )

        for manufacturer in self.manufacturer_data:
            if manufacturer in MANUFACTURERS:
                name: str = MANUFACTURERS[manufacturer]
                return name
        return None

    @cached_property
    def manufacturer_id(self) -> int | None:
        """Get the first manufacturer id."""
        for manufacturer in self.manufacturer_data:
            return manufacturer
        return None
