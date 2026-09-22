"""Parsing of Matter commissionable BLE advertisements."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from bluetooth_data_tools import parse_advertisement_data

if TYPE_CHECKING:
    from home_assistant_bluetooth import BluetoothServiceInfoBleak

MATTER_BLE_SERVICE_DATA_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"

_OPCODE_COMMISSIONABLE = 0x00


@dataclass(frozen=True, slots=True)
class MatterBleAdvertisement:
    """Decoded Matter commissionable advertisement (Matter Core spec 5.4.2.5.6)."""

    discriminator: int
    vendor_id: int
    product_id: int

    @property
    def unique_id(self) -> str:
        """Return a stable identity that survives BLE address rotation."""
        return f"{self.vendor_id:04x}{self.product_id:04x}{self.discriminator:03x}"

    @classmethod
    def from_service_data(cls, data: bytes | None) -> Self | None:
        """Decode the 8 byte service data payload."""
        if data is None or len(data) < 8 or data[0] != _OPCODE_COMMISSIONABLE:
            return None
        return cls(
            discriminator=int.from_bytes(data[1:3], "little") & 0x0FFF,
            vendor_id=int.from_bytes(data[3:5], "little"),
            product_id=int.from_bytes(data[5:7], "little"),
        )

    @classmethod
    def from_service_info(cls, service_info: BluetoothServiceInfoBleak) -> Self | None:
        """Decode from the service data aggregated across a device's packets."""
        return cls.from_service_data(
            service_info.service_data.get(MATTER_BLE_SERVICE_DATA_UUID)
        )

    @classmethod
    def from_raw(cls, raw: bytes) -> Self | None:
        """Decode from a single raw packet, ignoring data from earlier packets."""
        return cls.from_service_data(
            parse_advertisement_data((raw,)).service_data.get(
                MATTER_BLE_SERVICE_DATA_UUID
            )
        )
