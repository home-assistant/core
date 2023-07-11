"""BleakGATTServiceESPHome."""
from __future__ import annotations

from aioesphomeapi.model import BluetoothGATTService
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.service import BleakGATTService


class BleakGATTServiceESPHome(BleakGATTService):
    """GATT Characteristic implementation for the ESPHome backend."""

    obj: BluetoothGATTService

    def __init__(self, obj: BluetoothGATTService) -> None:
        """Init a BleakGATTServiceESPHome."""
        super().__init__(obj)  # type: ignore[no-untyped-call]
        self.__characteristics: list[BleakGATTCharacteristic] = []
        self.__handle: int = self.obj.handle

    @property
    def handle(self) -> int:
        """Integer handle of this service."""
        return self.__handle

    @property
    def uuid(self) -> str:
        """UUID for this service."""
        return self.obj.uuid

    @property
    def characteristics(self) -> list[BleakGATTCharacteristic]:
        """List of characteristics for this service."""
        return self.__characteristics

    def add_characteristic(self, characteristic: BleakGATTCharacteristic) -> None:
        """Add a :py:class:`~BleakGATTCharacteristicESPHome` to the service.

        Should not be used by end user, but rather by `bleak` itself.
        """
        self.__characteristics.append(characteristic)
