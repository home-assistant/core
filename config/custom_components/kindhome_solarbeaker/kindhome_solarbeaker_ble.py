import logging
from enum import Enum

from bleak import BleakClient, BLEDevice, BleakGATTCharacteristic

from config.custom_components.kindhome_solarbeaker.const import SERVICE_UUID
from config.custom_components.kindhome_solarbeaker.utils import log
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

MOVE_CHAR_UUID = "6acf4f08-cc9d-d495-6b41-aa7e60c4e8a6"
GET_MOTOR_STATE_CHAR_UUID = "d3d46a35-4394-e9aa-5a43-e7921120aaed"
GET_ACCELEROMETER_STATE_CHAR_UUID = "6d5c4b3a-2f1e-0d9c-8b7a-6f5e4d3c2b1a"
SECURITY_CODE = 0x45  # Hard coded for now


class KindhomeSolarbeakerState(Enum):
    MOTOR_STOP = 0
    MOTOR_FORWARD = 1
    MOTOR_BACKWARD = 2
    OPENED = 3
    CLOSED = 4
    UNDEFINED = -1


class KindhomeSolarBeakerData:
    pass


class KindhomeBluetoothDevice:
    def _publish_update(self):
        for c in self._callbacks:
            c()

    def state_byte_to_state_enum(self, value):
        log(_LOGGER, "state_byte_to_state_enum", f"value={value}")
        for state in KindhomeSolarbeakerState:
            log(_LOGGER, "state_byte_to_state_enum", f"{state}={state.value}")
            if state.value == value:
                return state
        return KindhomeSolarbeakerState.UNDEFINED

    async def _subscribe_to_state(self):
        def _state_notification_callback(sender: BleakGATTCharacteristic, data: bytearray):
            log(_LOGGER, "_state_notification_callback", f"state data: {sender}: {data}")
            assert len(data) == 1
            new_state = self.state_byte_to_state_enum(int.from_bytes(data, "little"))
            log(_LOGGER, "_state_notification_callback", f"{new_state}")
            self.state = new_state
            self._publish_update()

        await self.bleak_client.start_notify(GET_MOTOR_STATE_CHAR_UUID, _state_notification_callback)

    def __init__(self, ble_device: BLEDevice):
        self.address = ble_device.address
        self.ble_device = ble_device

        self.bleak_client = BleakClient(self.ble_device)
        self._callbacks = set()
        self.state: KindhomeSolarbeakerState = KindhomeSolarbeakerState.MOTOR_STOP

    def get_device_name(self) -> str:
        return "Test name"

    def available(self):
        return True

    async def connect(self):
        await self.bleak_client.connect()
        await self.bleak_client.pair()
        log(_LOGGER, "connect", "paired!")
        await self._subscribe_to_state()
        log(_LOGGER, "subscribed to state", "!")

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
    return SERVICE_UUID in data.service_uuids
