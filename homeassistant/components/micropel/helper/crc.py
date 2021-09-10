"""CRC sum."""
from .convert import int_to_hex


class CRC:
    """CRC support."""

    @staticmethod
    def get_crc_sum(message: str) -> str:
        """Get CRC sum of message."""
        checksum = 0
        for byte in bytes(message, "ascii"):
            checksum += byte
        checksum %= 256
        return int_to_hex(checksum, 2)
