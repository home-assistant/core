"""Encryption for MotionBlinds BLE."""
from __future__ import annotations

import datetime
from datetime import tzinfo

from Crypto.Cipher import AES
from Crypto.Cipher._mode_ecb import EcbMode
from Crypto.Util.Padding import pad, unpad
from pytz import timezone


class MotionCrypt:
    """Used for the encryption & decryption of bluetooth messages."""

    tz: tzinfo | None = None

    encryption_key: bytes = b"a3q8r8c135sqbn66"
    cipher: EcbMode = AES.new(encryption_key, AES.MODE_ECB)

    @staticmethod
    def set_timezone(tz: str) -> None:
        """Set the timezone for encryption, using a string like 'Europe/Amsterdam'."""
        MotionCrypt.tz = timezone(tz)

    @staticmethod
    def encrypt(plaintext_hex: str) -> str:
        """Encrypt a hex string."""
        plaintext_bytes = bytes.fromhex(plaintext_hex)
        cipheredtext_bytes = MotionCrypt.cipher.encrypt(
            pad(plaintext_bytes, AES.block_size)
        )
        cipheredtext_hex = cipheredtext_bytes.hex()
        return cipheredtext_hex

    @staticmethod
    def decrypt(cipheredtext_hex: str) -> str:
        """Decrypt a hex string."""
        cipheredtext_bytes = bytes.fromhex(cipheredtext_hex)
        plaintext_bytes = unpad(
            MotionCrypt.cipher.decrypt(cipheredtext_bytes), AES.block_size
        )
        plaintext_hex = plaintext_bytes.hex()
        return plaintext_hex

    @staticmethod
    def _format_hex(number: int, number_of_chars: int = 2) -> str:
        """Format a number as a hex string with a given number of characters."""
        return hex(number & 2 ** (number_of_chars * 4) - 1)[2:].zfill(number_of_chars)

    @staticmethod
    def get_time() -> str:
        """Get the current time string."""
        if not MotionCrypt.tz:
            raise TimezoneNotSetException(
                "Motion encryption requires a valid timezone."
            )
        now = datetime.datetime.now(MotionCrypt.tz)

        year = now.year % 100
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        microsecond = now.microsecond // 1000

        year_hex = MotionCrypt._format_hex(year)
        month_hex = MotionCrypt._format_hex(month)
        day_hex = MotionCrypt._format_hex(day)
        hour_hex = MotionCrypt._format_hex(hour)
        minute_hex = MotionCrypt._format_hex(minute)
        second_hex = MotionCrypt._format_hex(second)
        microsecond_hex = MotionCrypt._format_hex(microsecond, number_of_chars=4)

        return (
            year_hex
            + month_hex
            + day_hex
            + hour_hex
            + minute_hex
            + second_hex
            + microsecond_hex
        )


class TimezoneNotSetException(Exception):
    """Error to indicate the timezone was not set."""
