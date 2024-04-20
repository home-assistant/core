"""Helpers to generate uuids."""

from random import getrandbits


def random_uuid_hex() -> str:
    """Generate a random UUID hex.

    This uuid should not be used for cryptographically secure
    operations.
    """
    random_bits = getrandbits(32 * 4)
    return f"{random_bits:032x}"
