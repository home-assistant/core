from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from custom_components.ryse.bluetooth import RyseBLEDevice
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    device = RyseBLEDevice(
        entry.data["address"], entry.data["rx_uuid"], entry.data["tx_uuid"]
    )
    async_add_entities([SmartShadeCover(device)])


def build_position_packet(pos: int) -> bytes:
    """Convert MAC address to reversed hex array, prepend a prefix with a position last byte, and append a checksum."""

    # Ensure position is a valid byte (0-100)
    if not (0 <= pos <= 100):
        raise ValueError("position must be between 0 and 100")

    data_bytes = bytes([0xF5, 0x03, 0x01, 0x01, pos])

    # Compute checksum (sum of bytes from the 3rd byte onward, modulo 256)
    checksum = sum(data_bytes[2:]) % 256

    # Append checksum
    return data_bytes + bytes([checksum])


def build_get_position_packet() -> bytes:
    """Build raw data to send to the RYSE ble device to retrieve current position"""

    data_bytes = bytes([0xF5, 0x02, 0x01, 0x03])

    # Compute checksum (sum of bytes from the 3rd byte onward, modulo 256)
    checksum = sum(data_bytes[2:]) % 256

    # Append checksum
    return data_bytes + bytes([checksum])


class SmartShadeCover(CoverEntity):
    def __init__(self, device):
        self._device = device
        self._attr_name = f"Smart Shade {device.address}"
        self._attr_unique_id = f"smart_shade_{device.address}"
        self._state = None
        self._current_position = None

        # Register the callback
        self._device.update_callback = self._update_position

    @property
    def device_info(self):
        return {
            "identifiers": {(self._device.address,)},
            "name": f"Smart Shade {self._device.address}",
            "manufacturer": "RYSE",
            "model": "SmartShade BLE",
            "connections": {("bluetooth", self._device.address)},
        }

    async def _update_position(self, position):
        """Update cover position when receiving notification."""
        if 0 <= position <= 100:
            self._current_position = 100 - position
            self._state = "open" if position < 100 else "closed"
            _LOGGER.debug(f"Updated cover position: {position}")
        self.async_write_ha_state()  # Notify Home Assistant about the state change

    async def async_open_cover(self, **kwargs):
        """Open the shade."""
        pdata = build_position_packet(0x00)
        await self._device.write_data(pdata)
        _LOGGER.debug(f"Binary packet to change position to open")
        self._state = "open"

    async def async_close_cover(self, **kwargs):
        """Close the shade."""
        pdata = build_position_packet(0x64)
        await self._device.write_data(pdata)
        _LOGGER.debug(f"Binary packet to change position to close")
        self._state = "closed"

    async def async_set_cover_position(self, **kwargs):
        """Set the shade to a specific position."""
        position = 100 - kwargs.get("position", 0)
        pdata = build_position_packet(position)
        await self._device.write_data(pdata)
        _LOGGER.debug(f"Binary packet to change position to a specific position")
        self._state = "open" if position < 100 else "closed"

    async def async_update(self):
        """Fetch the current state and position from the device."""
        if not self._device.client or not self._device.client.is_connected:
            paired = await self._device.pair()
            if not paired:
                _LOGGER.warning("Failed to pair with device. Skipping update.")
                return

        try:
            if self._current_position is None:
                bytesinfo = build_get_position_packet()
                await self._device.write_data(bytesinfo)
        except Exception as e:
            _LOGGER.error(f"Error reading device data: {e}")

    @property
    def is_closed(self):
        return self._state == "closed"

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        if self._current_position is None:
            return 50
        if not (0 <= self._current_position <= 100):
            _LOGGER.warning(
                f"Invalid position value detected: {self._current_position}"
            )
            return 50  # Prevent invalid values
        return int(self._current_position)

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )
