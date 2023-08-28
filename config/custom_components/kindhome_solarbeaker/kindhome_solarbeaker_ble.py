import logging

from bleak import BleakClient, BLEDevice

from config.custom_components.kindhome_solarbeaker.utils import log
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

MOVE_CHAR_UUID = "6acf4f08-cc9d-d495-6b41-aa7e60c4e8a6"
GET_MOTOR_STATE_CHAR_UUID = "d3d46a35-4394-e9aa-5a43-e7921120aaed"
GET_ACCELEROMETER_STATE_CHAR_UUID = "6d5c4b3a-2f1e-0d9c-8b7a-6f5e4d3c2b1a"
SECURITY_CODE = 0x45  # Hard coded for now


class KindhomeSolarBeakerData:
    pass


class KindhomeBluetoothDevice:
    def __init__(self, ble_device: BLEDevice):
        self.address = ble_device.address
        self.ble_device = ble_device

        self.bleak_client = BleakClient(self.ble_device)
        self._callbacks = set()

    def get_device_name(self) -> str:
        return "Test name"

    def available(self):
        return True

    async def connect(self):
        await self.bleak_client.connect()
        await self.bleak_client.pair()
        log(_LOGGER, "connect", "paired!")

    async def move_forward(self):
        await self.bleak_client.write_gatt_char(MOVE_CHAR_UUID, bytearray([1, SECURITY_CODE]))

    async def move_backward(self):
        await self.bleak_client.write_gatt_char(MOVE_CHAR_UUID, bytearray([2, SECURITY_CODE]))

    async def stop(self):
        await self.bleak_client.write_gatt_char(MOVE_CHAR_UUID, bytearray([0, SECURITY_CODE]))

    # async def poll_data(self) -> KindhomeSolarBeakerData:
    #     pass

    def register_callback(self, callback):
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        self._callbacks.discard(callback)


def supported(data: BluetoothServiceInfoBleak) -> bool:
    return True
    # return SERVICE_UUID in data.service_uuids
