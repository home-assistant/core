"""BleakGATTCharacteristicESPHome."""
from __future__ import annotations

import contextlib
from uuid import UUID

from aioesphomeapi.model import BluetoothGATTCharacteristic
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor

_GattCharacteristicsPropertiesEnum: dict[int | None, tuple[str, str]] = {
    None: ("None", "The characteristic doesn’t have any properties that apply"),
    1: ("Broadcast".lower(), "The characteristic supports broadcasting"),
    2: ("Read".lower(), "The characteristic is readable"),
    4: (
        "Write-Without-Response".lower(),
        "The characteristic supports Write Without Response",
    ),
    8: ("Write".lower(), "The characteristic is writable"),
    16: ("Notify".lower(), "The characteristic is notifiable"),
    32: ("Indicate".lower(), "The characteristic is indicatable"),
    64: (
        "Authenticated-Signed-Writes".lower(),
        "The characteristic supports signed writes",
    ),
    128: (
        "Extended-Properties".lower(),
        "The ExtendedProperties Descriptor is present",
    ),
    256: ("Reliable-Writes".lower(), "The characteristic supports reliable writes"),
    512: (
        "Writable-Auxiliaries".lower(),
        "The characteristic has writable auxiliaries",
    ),
}


class BleakGATTCharacteristicESPHome(BleakGATTCharacteristic):
    """GATT Characteristic implementation for the ESPHome backend."""

    obj: BluetoothGATTCharacteristic

    def __init__(
        self,
        obj: BluetoothGATTCharacteristic,
        max_write_without_response_size: int,
        service_uuid: str,
        service_handle: int,
    ) -> None:
        """Init a BleakGATTCharacteristicESPHome."""
        super().__init__(obj, max_write_without_response_size)
        self.__descriptors: list[BleakGATTDescriptor] = []
        self.__service_uuid: str = service_uuid
        self.__service_handle: int = service_handle
        self.__props: list[str] = [
            _GattCharacteristicsPropertiesEnum[v][0]
            for v in [2**n for n in range(10)]
            if (self.obj.properties & v)
        ]

    @property
    def service_uuid(self) -> str:
        """Uuid of the Service containing this characteristic."""
        return self.__service_uuid

    @property
    def service_handle(self) -> int:
        """Integer handle of the Service containing this characteristic."""
        return self.__service_handle

    @property
    def handle(self) -> int:
        """Integer handle for this characteristic."""
        return self.obj.handle

    @property
    def uuid(self) -> str:
        """Uuid of this characteristic."""
        return self.obj.uuid

    @property
    def properties(self) -> list[str]:
        """Properties of this characteristic."""
        return self.__props

    @property
    def descriptors(self) -> list[BleakGATTDescriptor]:
        """List of descriptors for this service."""
        return self.__descriptors

    def get_descriptor(self, specifier: int | str | UUID) -> BleakGATTDescriptor | None:
        """Get a descriptor by handle (int) or UUID (str or uuid.UUID)."""
        with contextlib.suppress(StopIteration):
            if isinstance(specifier, int):
                return next(filter(lambda x: x.handle == specifier, self.descriptors))
            return next(filter(lambda x: x.uuid == str(specifier), self.descriptors))
        return None

    def add_descriptor(self, descriptor: BleakGATTDescriptor) -> None:
        """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

        Should not be used by end user, but rather by `bleak` itself.
        """
        self.__descriptors.append(descriptor)
