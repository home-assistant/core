"""BleakGATTDescriptorESPHome."""
from __future__ import annotations

from aioesphomeapi.model import BluetoothGATTDescriptor
from bleak.backends.descriptor import BleakGATTDescriptor


class BleakGATTDescriptorESPHome(BleakGATTDescriptor):
    """GATT Descriptor implementation for ESPHome backend."""

    obj: BluetoothGATTDescriptor

    def __init__(
        self,
        obj: BluetoothGATTDescriptor,
        characteristic_uuid: str,
        characteristic_handle: int,
    ) -> None:
        """Init a BleakGATTDescriptorESPHome."""
        super().__init__(obj)
        self.__characteristic_uuid: str = characteristic_uuid
        self.__characteristic_handle: int = characteristic_handle

    @property
    def characteristic_handle(self) -> int:
        """Handle for the characteristic that this descriptor belongs to."""
        return self.__characteristic_handle

    @property
    def characteristic_uuid(self) -> str:
        """UUID for the characteristic that this descriptor belongs to."""
        return self.__characteristic_uuid

    @property
    def uuid(self) -> str:
        """UUID for this descriptor."""
        return self.obj.uuid

    @property
    def handle(self) -> int:
        """Integer handle for this descriptor."""
        return self.obj.handle
