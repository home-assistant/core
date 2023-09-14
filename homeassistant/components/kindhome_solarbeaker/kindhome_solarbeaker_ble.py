"""File that will be moved to kindhome_ble pypi library."""

from collections.abc import Callable
import dataclasses
from enum import Enum
import logging

from bleak import BleakClient, BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .utils import log

_LOGGER = logging.getLogger(__name__)


SERVICE_UUID = "75c276c3-8f97-20bc-a143-b354244886d4"
MOVE_CHAR_UUID = "6acf4f08-cc9d-d495-6b41-aa7e60c4e8a6"
GET_MOTOR_STATE_CHAR_UUID = "d3d46a35-4394-e9aa-5a43-e7921120aaed"
SECURITY_CODE = 0x45  # Hard coded for now

GET_BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


class KindhomeSolarbeakerMotorState(Enum):
    """Represents state of motor."""

    MOTOR_STOP = 0
    MOTOR_FORWARD = 1
    MOTOR_BACKWARD = 2
    OPENED = 3
    CLOSED = 4
    UNDEFINED = -1

    @staticmethod
    def state_byte_to_state_enum(value):
        """Get enum instance from motor state enum value."""
        log(_LOGGER, "state_byte_to_state_enum", f"value={value}")
        for state in KindhomeSolarbeakerMotorState:
            if state.value == value:
                log(_LOGGER, "state_byte_to_state_enum", f"{state}={state.value}")
                return state
        return KindhomeSolarbeakerMotorState.UNDEFINED


@dataclasses.dataclass
class KindhomeSolarBeakerState:
    """Contains state data returned from the device."""

    motor_state: KindhomeSolarbeakerMotorState
    battery_level: int


class KindhomeSolarbeakerDevice:
    """Represents a Kindhome Solarbeaker bluetooth device."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialize the device data (without connecting)."""
        self.ble_device = ble_device

        self.bleak_client = BleakClient(self.ble_device)
        self._callbacks: set[Callable[[], None]] = set()
        self.device_name = ble_device.name
        self.state: KindhomeSolarBeakerState = KindhomeSolarBeakerState(
            KindhomeSolarbeakerMotorState.UNDEFINED, 0
        )

    def _publish_updates(self):
        for c in self._callbacks:
            c()

    async def _subscribe_to_motor(self):
        def _motor_state_notification_callback(sender, data: bytearray):
            log(
                _LOGGER,
                "_motor_state_notification_callback",
                f"state data: {sender}: {data}",
            )
            assert len(data) == 1
            new_motor_state = KindhomeSolarbeakerMotorState.state_byte_to_state_enum(
                int.from_bytes(data, "little")
            )
            log(_LOGGER, "_motor_state_notification_callback", f"{new_motor_state}")
            self.state = dataclasses.replace(self.state, motor_state=new_motor_state)
            self._publish_updates()

        await self.bleak_client.start_notify(
            GET_MOTOR_STATE_CHAR_UUID, _motor_state_notification_callback
        )

    async def _subscribe_to_battery(self):
        def _battery_notification_callback(sender, data: bytearray):
            log(_LOGGER, "_battery_notification_callback", f"data: {sender}: {data}")
            assert len(data) == 1
            battery_level_percentage = data[0]
            self.state = dataclasses.replace(
                self.state, battery_level=battery_level_percentage
            )
            self._publish_updates()

        await self.bleak_client.start_notify(
            GET_BATTERY_LEVEL_CHAR_UUID, _battery_notification_callback
        )

    async def _subscribe_to_state_changes(self):
        await self._subscribe_to_motor()
        await self._subscribe_to_battery()

    @property
    def battery_level(self):
        """Return device battery level."""
        return self.state.battery_level

    @property
    def device_id(self):
        """Return unique device id."""
        return f"kindhome_solarbeaker_{self.ble_device.address}"

    # def available(self):
    #     return True

    async def connect(self):
        """Connect and pair the device."""
        await self.bleak_client.connect()
        await self.bleak_client.pair()
        log(_LOGGER, "connect", "paired!")

    async def get_state_and_subscribe_to_changes(self):
        """Get initial device state and subscribe to notification about state changes sent by device."""
        assert self.bleak_client.is_connected

        # I dont know how to get initial state!
        # initial_motor_state_val = await self.bleak_client.read_gatt_char(GET_MOTOR_STATE_CHAR_UUID)
        # initial_motor_state_enum = KindhomeSolarbeakerMotorState.state_byte_to_state_enum(initial_motor_state_val)
        #
        # initial_battery_level_bytes = await self.bleak_client.read_gatt_char(GET_BATTERY_LEVEL_CHAR_UUID)
        # initial_battery = initial_battery_level_bytes[0]

        self.state = KindhomeSolarBeakerState(
            KindhomeSolarbeakerMotorState.UNDEFINED, 0
        )
        await self._subscribe_to_state_changes()
        log(_LOGGER, "subscribed to state", "!")

    async def move_forward(self):
        """Send signal for motor to move forward."""
        await self.bleak_client.write_gatt_char(
            MOVE_CHAR_UUID, bytearray([1, SECURITY_CODE])
        )

    async def move_backward(self):
        """Send signal for motor to move backward."""
        await self.bleak_client.write_gatt_char(
            MOVE_CHAR_UUID, bytearray([2, SECURITY_CODE])
        )

    async def stop(self):
        """Send signal for motor to stop."""
        await self.bleak_client.write_gatt_char(
            MOVE_CHAR_UUID, bytearray([0, SECURITY_CODE])
        )

    def register_callback(self, callback):
        """Register callback called when state changes."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove callback. Doesn't do anything if callback wasn't registered."""
        self._callbacks.discard(callback)

    @staticmethod
    def supported(data: BluetoothServiceInfoBleak) -> bool:
        """Check if detected bluetooth service represents a Kindhome Solarbeaker Device."""
        return SERVICE_UUID in data.service_uuids
