import asyncio
from bleak import BleakClient, BleakScanner
import logging

_LOGGER = logging.getLogger(__name__)


class RyseBLEDevice:
    def __init__(self, address=None, rx_uuid=None, tx_uuid=None):
        self.address = address
        self.rx_uuid = rx_uuid
        self.tx_uuid = tx_uuid
        self.client = None

    async def pair(self):
        if not self.address:
            _LOGGER.error("No device address provided for pairing.")
            return False
        _LOGGER.debug(f"Pairing with device {self.address}")
        self.client = BleakClient(self.address)
        try:
            await self.client.connect(timeout=30.0)
            if self.client.is_connected:
                _LOGGER.debug(f"Successfully paired with {self.address}")
                # Subscribe to notifications
                await self.client.start_notify(self.rx_uuid, self._notification_handler)
                return True
        except Exception as e:
            _LOGGER.error(
                f"Error pairing with device {self.address}: {e}", exc_info=True
            )
        return False

    async def _notification_handler(self, sender, data):
        """Callback function for handling received BLE notifications."""
        if len(data) >= 5 and data[0] == 0xF5 and data[2] == 0x01 and data[3] == 0x18:
            # ignore REPORT USER TARGET data
            return
        _LOGGER.debug(f"Received notification")
        if len(data) >= 5 and data[0] == 0xF5 and data[2] == 0x01 and data[3] == 0x07:
            new_position = data[4]  # Extract the position byte
            _LOGGER.debug(
                f"Received valid notification, updating position: {new_position}"
            )

            # Notify cover.py about the position update
            if hasattr(self, "update_callback"):
                await self.update_callback(new_position)

    async def get_device_info(self):
        if self.client:
            try:
                manufacturer_data = self.client.services
                _LOGGER.debug(f"Getting Manufacturer Data")
                return manufacturer_data
            except Exception as e:
                _LOGGER.error(f"Failed to get device info: {e}")
        return None

    async def unpair(self):
        if self.client:
            await self.client.disconnect()
            _LOGGER.debug("Device disconnected")
            self.client = None

    async def read_data(self):
        if self.client:
            data = await self.client.read_gatt_char(self.rx_uuid)
            if len(data) < 5 or data[0] != 0xF5 or data[2] != 0x01 or data[3] != 0x18:
                # ignore REPORT USER TARGET data
                _LOGGER.debug(f"Received Position Report Data")
                return data
            return None

    async def write_data(self, data):
        if self.client:
            await self.client.write_gatt_char(self.tx_uuid, data)
            _LOGGER.debug(f"Sending data to tx uuid")

    async def scan_and_pair(self):
        _LOGGER.debug("Scanning for BLE devices...")
        devices = await BleakScanner.discover()
        for device in devices:
            _LOGGER.debug(f"Found device: {device.name} ({device.address})")
            if device.name and "target-device-name" in device.name.lower():
                _LOGGER.debug(
                    f"Attempting to pair with {device.name} ({device.address})"
                )
                self.address = device.address
                return await self.pair()
        _LOGGER.warning("No suitable devices found to pair")
        return False
