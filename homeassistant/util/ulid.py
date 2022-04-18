"""Helpers to generate ulids."""

from random import getrandbits
import time


def ulid_hex() -> str:
    """Generate a ULID in hex that will work for a UUID.

    This ulid should not be used for cryptographically secure
    operations.

     01AN4Z07BY      79KA1307SR9X4MV3
    |----------|    |----------------|
     Timestamp          Randomness
       48bits             80bits

    This string can be converted with https://github.com/ahawker/ulid

    ulid.from_uuid(uuid.UUID(value))
    """
    return f"{int(time.time()*1000):012x}{getrandbits(80):020x}"
