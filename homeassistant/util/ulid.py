"""Helpers to generate ulids."""

from random import getrandbits
import time


def ulid_hex() -> str:
    """Generate a ULID in hex.

     01AN4Z07BY      79KA1307SR9X4MV3
    |----------|    |----------------|
     Timestamp          Randomness
       48bits             80bits

    """
    return f'{int.to_bytes(int(time.time()*1000), 6, "big").hex().zfill(6)}{getrandbits(80):010x}'
