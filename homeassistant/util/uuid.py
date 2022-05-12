"""Helpers to generate uuids."""

from random import getrandbits


def random_uuid_hex() -> str:
    """Generate a random UUID hex.

    This uuid should not be used for cryptographically secure
    operations.
    """
    return "%032x" % getrandbits(32 * 4)
