"""Helper for parsing of messages."""
from typing import Optional

from .convert import int_to_hex
from .crc import CRC
from .exceptions import InvalidMessageError


def _get_cmd_index(message):
    cmd_index = None
    if "*" in message:
        cmd_index = message.index("*")
    if "!" in message:
        cmd_index = message.index("!")
    return cmd_index + 1


def _get_crc_index(message):
    if "#" in message:
        return message.index("#") + 1
    return None


class Message:
    """Message helper."""

    @staticmethod
    def is_valid_message(message: str) -> bool:
        """Check if message is valid."""
        return (message is None) or (len(message) < 6)

    @staticmethod
    def build_message(plc: int, cmd_type: str, cmd_id: int, data: str) -> str:
        """Build message."""
        message = ""
        if plc is not None:
            message += "@" + int_to_hex(plc, 2)
        message += cmd_type + int_to_hex(cmd_id, 2)
        if data is not None:
            message += data
        message += "#" + CRC.get_crc_sum(message)
        return message.upper()

    @staticmethod
    def get_crc(message: str) -> Optional[str]:
        """Return CRC from message."""
        if Message.is_valid_message(message):
            raise InvalidMessageError(message)
        message = message.replace("\r", "")
        crc_index = _get_crc_index(message)
        crc = message[crc_index:]
        return crc

    @staticmethod
    def get_plc_address(message: str) -> Optional[str]:
        """Return PLC address from message."""
        plc = None
        if Message.is_valid_message(message):
            raise InvalidMessageError(message)
        message = message.replace("\r", "")
        if message.startswith("@"):
            plc = message[1:3]
        return plc

    @staticmethod
    def get_cmd_id(message: str) -> Optional[str]:
        """Return CMD ID from message."""
        if Message.is_valid_message(message):
            raise InvalidMessageError(message)
        message = message.replace("\r", "")
        cmd_index = _get_cmd_index(message)
        cmd_id = None
        if cmd_index is not None:
            cmd_id = message[cmd_index : cmd_index + 2]
        return cmd_id

    @staticmethod
    def get_data(message: str) -> Optional[str]:
        """Return DATA from message."""
        if Message.is_valid_message(message):
            raise InvalidMessageError(message)
        message = message.replace("\r", "")

        crc_index = _get_crc_index(message)
        cmd_index = _get_cmd_index(message)
        data = message[cmd_index + 2 : crc_index - 1]
        if len(data) < 1:
            return None
        return data

    @staticmethod
    def get_cmd_type(message: str) -> Optional[str]:
        """Return CMD type from message."""
        if Message.is_valid_message(message):
            raise InvalidMessageError(message)
        message = message.replace("\r", "")

        cmd_index = _get_cmd_index(message)
        cmd_type = message[cmd_index - 1 : cmd_index]
        return cmd_type
