"""Helpers to generate uuids."""

from random import getrandbits
import secrets


def random_uuid_hex() -> str:
    """Generate a random UUID hex.

    This uuid should not be used for cryptographically secure
    operations.
    """
    return f"{getrandbits(32 * 4):032x}"


def secure_uuid_hex() -> str:
    """Generate an unpredictable random UUID hex.

    Use this for an ID that grants access to whoever knows it.
    """
    return secrets.token_hex(16)
