"""Defines the AirTouchMessage class for building and modifying messages sent to the AirTouch system."""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class AirTouchMessage:
    """Builds various message types for the AirTouch system."""

    def __init__(self) -> None:
        """Initialize a new AirTouchMessage instance.

        The default buffer is 13 bytes long, and `sum_byte` is used for checksum calculations.
        """
        self.buffer = bytearray(13)
        self.sum_byte = bytearray(13)
        self._is_temp = False

    @property
    def is_temp(self) -> bool:
        """Indicates whether this message pertains to a temperature-related command."""
        return self._is_temp

    @is_temp.setter
    def is_temp(self, value: bool) -> None:
        """Set whether this message is temperature-related.

        :param value: True if temperature-related, otherwise False.
        """
        self._is_temp = value

    def reset_message(self) -> None:
        """Reset the internal message buffer to default values.

        Sets the first byte to 85 (0x55) and the third byte to 12 (0x0C).
        """
        for i in range(13):
            self.buffer[i] = 0
        self.buffer[0] = 85
        self.buffer[2] = 12

    def print_hex_code(self) -> None:
        """Log the internal message buffer in hex format for debugging."""
        _LOGGER.debug(",".join(format(x, "02x") for x in self.buffer))

    def calc_checksum(self) -> int:
        """Calculate an 8-bit checksum of the first 12 bytes of the buffer."""
        self.sum_byte[:] = self.buffer
        return sum(b & 0xFF for b in self.sum_byte[:-1]) % 256

    def get_init_msg(self) -> bytearray:
        """Create an initialization message buffer (13 bytes)."""
        self.reset_message()
        self.buffer[1] = 1
        self.buffer[12] = self.calc_checksum()
        return self.buffer

    def toggle_zone(self, zone: int) -> bytearray:
        """Create a command to toggle power on/off for a specific zone.

        :param zone: The zone index to toggle.
        :return: A 13-byte buffer for the toggle_zone command.
        """
        self.reset_message()
        self.buffer[1] = 129  # -127 as unsigned
        self.buffer[3] = zone
        self.buffer[4] = 128  # -128 as unsigned
        self.buffer[12] = self.calc_checksum()
        return self.buffer

    def set_fan(self, room: int, inc_dec: int) -> bytearray:
        """Create a command to increment or decrement the fan/temperature setting for a given room.

        :param room: The room or zone index.
        :param inc_dec: Positive to increment temperature; negative to decrement.
        :return: A 13-byte buffer with the fan adjustment command.
        """
        self.reset_message()
        self.buffer[1] = 129  # -127 as unsigned
        self.buffer[3] = room
        self.buffer[4] = 2 if inc_dec >= 0 else 1
        self.buffer[5] = 1
        self.buffer[12] = self.calc_checksum()
        return self.buffer

    def toggle_ac_on_off(self, ac_id: int) -> bytearray:
        """Create a command to toggle the AC on/off.

        :param ac_id: The AirTouch AC identifier.
        :return: A 13-byte buffer with the toggle command.
        """
        _LOGGER.debug("Toggling AC for id %d", ac_id)
        self.reset_message()
        self.buffer[1] = 134  # -122 as unsigned
        self.buffer[3] = ac_id
        self.buffer[4] = 128  # -128 as unsigned
        self.buffer[12] = self.calc_checksum()
        return self.buffer

    def set_mode(self, ac_id: int, brand_id: int, in_mode: Any) -> bytearray:
        """Create a command to set the AC mode (e.g., cool, heat, auto).

        :param ac_id: AirTouch AC identifier.
        :param brand_id: AC brand identifier, for special offsets.
        :param in_mode: Mode, castable to int.
        :return: A 13-byte buffer with the mode-setting command.
        """
        self.reset_message()
        mode = int(in_mode)  # Ensure it's an integer

        # Brand-specific remapping
        if ac_id == 0 and brand_id == 11:
            mode = {0: 0, 1: 2, 2: 3, 3: 4, 4: 1}.get(mode, mode)

        if ac_id == 0 and brand_id == 15:
            mode = {0: 5, 1: 2, 2: 3, 3: 4, 4: 1}.get(mode, mode)

        _LOGGER.debug(
            "Air Conditioner brand id at mode select: %d and mode %d", brand_id, mode
        )
        self.buffer[1] = 134  # -122 as unsigned
        self.buffer[3] = ac_id
        self.buffer[4] = 129  # -127 as unsigned
        self.buffer[5] = mode

        _LOGGER.debug("Checksum is %d", self.calc_checksum())
        self.buffer[12] = self.calc_checksum()
        return self.buffer

    def set_fan_speed(self, ac_id: int, brand_id: int, in_mode: Any) -> bytearray:
        """Create a command to set the fan speed for the AC unit.

        :param ac_id: AirTouch AC identifier.
        :param brand_id: AC brand identifier, used for certain speed mappings.
        :param in_mode: Fan speed, castable to int.
        :return: A 13-byte buffer with the fan speed-setting command.
        """
        self.reset_message()
        mode = int(in_mode)  # Ensure it's an integer

        if ac_id == 0 and brand_id == 15 and mode == 0:
            mode = 4
        if ac_id == 0 and brand_id == 2:
            mode = {0: 0, 4: 1}.get(mode, mode + 1)

        _LOGGER.debug("Final mode sending for fan speed: %d", mode)
        self.buffer[1] = 134  # -122 as unsigned
        self.buffer[3] = ac_id
        self.buffer[4] = 130  # -126 as unsigned
        self.buffer[5] = mode
        self.buffer[12] = self.calc_checksum()
        return self.buffer
