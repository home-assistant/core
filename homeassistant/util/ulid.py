"""Helpers to generate ulids."""

from random import getrandbits
import time


def ulid_hex() -> str:
    """Generate a ULID in hex.

    This ulid should not be used for cryptographically secure
    operations.

     01AN4Z07BY      79KA1307SR9X4MV3
    |----------|    |----------------|
     Timestamp          Randomness
       48bits             80bits

    """
    return f"{int(time.time()*1000):012x}{getrandbits(80):020x}"
