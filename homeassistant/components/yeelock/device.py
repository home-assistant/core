"""Yeelock device."""

from binascii import hexlify
import hashlib
import hmac
import logging
from time import time
import uuid

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.const import CONF_API_KEY, CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOCKER_KIND, UUID_COMMAND, UUID_NOTIFY

_LOGGER = logging.getLogger(__name__)


class YeelockDeviceEntity:
    """Entity class for the Yeelock devices."""

    _attr_has_entity_name = True

    def __init__(self, yeelock_device, hass: HomeAssistant):
        """Init entity with the device."""
        self.hass = hass
        self.device: Yeelock = yeelock_device
        self._attr_unique_id = f"{yeelock_device.mac}_{self.__class__.__name__}"

    @property
    def device_info(self):
        """Shared device info information."""
        return {
            "identifiers": {(DOMAIN, self.device.mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            "name": self.device.name,
            "manufacturer": self.device.manufacturer,
            "model": self.device.model,
        }


class Yeelock:
    """Yeelock class."""

    def __init__(self, config: dict, hass: HomeAssistant) -> None:
        """Initialize device."""
        self._hass = hass
        self._device = None
        self._lock = None
        self._client = None
        self._connecting = False
        self._connected = False
        self.mac = config.get(CONF_MAC)
        self.name = config.get(CONF_NAME)
        self.key = config.get(CONF_API_KEY)
        self.model = config.get(CONF_MODEL, None)
        self.manufacturer = "Yeelock"

    async def disconnect(self):
        """Disconnect from the device."""
        _LOGGER.debug("Disconnected from %s", self.mac)
        if (self._client is not None) and self._client.is_connected:
            await self._client.disconnect()

    async def _connect(self):
        """Connect to the device.

        :raises BleakError: if the device is not found
        """
        self._connecting = True
        try:
            if (self._client is None) or (not self._client.is_connected):
                self._device = bluetooth.async_ble_device_from_address(
                    self._hass, self.mac, connectable=True
                )
                if not self._device:
                    raise BleakError(
                        f"A device with address {self.mac} could not be found."
                    )
                self._client = BleakClient(self._device)
                _LOGGER.debug("Connecting to %s", self.mac)
                await self._client.connect()
                _LOGGER.debug("Connected to %s", self.mac)
                await self._client.start_notify(
                    uuid.UUID(UUID_NOTIFY), self._handle_data
                )
                _LOGGER.debug("Listening for notifications from %s", self.mac)
        except Exception as error:
            self._connecting = False
            raise error
        self._connecting = False

    async def _handle_data(self, sender, value):
        """Handle data notifications."""
        _LOGGER.debug("Received %s from %s", hexlify(value, " "), sender)  # noqa: E501
        new_state = None

        # Hex the received message
        received_message = hexlify(value, " ")

        # Extract the first element (index 0) and convert it to an integer
        first_byte = hex(int(received_message.split()[0], 16))

        # Lock change successes
        # Unlocking
        if first_byte == hex(0x2):
            new_state = "unlocking"

        # Unlocked
        elif first_byte == hex(0x3):
            new_state = "unlocked"

        # Locking
        elif first_byte == hex(0x4):
            new_state = "locking"

        # Locked
        elif first_byte == hex(0x5):
            new_state = "locked"

        # Lock change failures
        # Invalid signing key
        elif first_byte == hex(0xFF):
            _LOGGER.error("Invalid signing key")
            new_state = "jammed"

        # Time needs to be synced
        elif first_byte == hex(0x9):
            _LOGGER.warning("Time needs to be synced")
            await self.time_sync()

        # Unknown notification received
        else:
            _LOGGER.warning("Unknown notification received")

        # Update to the new lock state, if we have one
        if new_state is not None:
            _LOGGER.debug("Notified of %s", new_state)
            await self._lock._update_lock_state(new_state)

    def _encrypt(self, unlock_mode):
        """Encrypt the data."""
        # Given values
        unlock_command = 0x01
        admin_identification_mode = 0x50
        key = bytearray.fromhex(self.key)

        # Convert epoch time to a human-readable date and time
        timestamp = int(time())

        # Generate the HMAC
        message = (
            unlock_command.to_bytes(1, "big")
            + admin_identification_mode.to_bytes(1, "big")
            + timestamp.to_bytes(4, "big")
            + int(unlock_mode, 16).to_bytes(1, "big")
        )
        hmac_result = bytearray.fromhex(
            hmac.new(key, message[:7], hashlib.sha1).hexdigest()
        )[:13]

        # Concatenate all the parts to create the output value as a bytearray
        output_value = (
            unlock_command.to_bytes(1, "big")
            + admin_identification_mode.to_bytes(1, "big")
            + timestamp.to_bytes(4, "big")
            + int(unlock_mode, 16).to_bytes(1, "big")
            + hmac_result
        )

        _LOGGER.debug("Sent transactional msg %s", output_value)
        return output_value

    def _encrypt_time(self):
        """Encrypt the time."""
        # Given values
        unlock_command = 0x08
        admin_identification_mode = 0x40
        key = bytearray.fromhex(self.key)

        # Convert epoch time to a human-readable date and time
        timestamp = int(time())

        # Generate the HMAC
        message = (
            unlock_command.to_bytes(1, "big")
            + admin_identification_mode.to_bytes(1, "big")
            + timestamp.to_bytes(4, "big")
        )
        hmac_result = bytearray.fromhex(
            hmac.new(key, message[:6], hashlib.sha1).hexdigest()
        )[:14]

        # Concatenate all the parts to create the output value as a bytearray
        output_value = (
            unlock_command.to_bytes(1, "big")
            + admin_identification_mode.to_bytes(1, "big")
            + timestamp.to_bytes(4, "big")
            + hmac_result
        )

        _LOGGER.debug("Sent time sync msg %s", output_value)
        return output_value

    async def locker(self, kind) -> None:
        """Lock, unlock and quick unlock the device."""
        await self._connect()
        try:
            _LOGGER.debug("Locking")
            await self._client.write_gatt_char(
                uuid.UUID(UUID_COMMAND), bytearray(self._encrypt(LOCKER_KIND[kind]))
            )
        except BleakError as error:
            self._connected = False
            _LOGGER.error("BleakError: %s", error)

    async def time_sync(self) -> None:
        """Time sync and retry."""
        await self._connect()
        try:
            # Sync the time
            _LOGGER.debug("Time sync start")
            await self._client.write_gatt_char(
                uuid.UUID(UUID_COMMAND), bytearray(self._encrypt_time())
            )

            # Retry the original action
            if self._lock._attr_state == "locking":
                await self.locker("lock")
            elif self._lock._attr_state == "unlocking":
                await self.locker("unlock")
        except BleakError as error:
            self._connected = False
            _LOGGER.error("BleakError: %s", error)
