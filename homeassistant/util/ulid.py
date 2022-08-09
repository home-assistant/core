"""Helpers to generate ulids."""
from __future__ import annotations

from random import getrandbits
import time


def ulid_hex() -> str:
    """Generate a ULID in lowercase hex that will work for a UUID.

    This ulid should not be used for cryptographically secure
    operations.

    This string can be converted with https://github.com/ahawker/ulid

    ulid.from_uuid(uuid.UUID(ulid_hex))
    """
    return f"{int(time.time()*1000):012x}{getrandbits(80):020x}"


def ulid(timestamp: float | None = None) -> str:
    """Generate a ULID.

    This ulid should not be used for cryptographically secure
    operations.

     01AN4Z07BY      79KA1307SR9X4MV3
    |----------|    |----------------|
     Timestamp          Randomness
       48bits             80bits

    This string can be loaded directly with https://github.com/ahawker/ulid

    import homeassistant.util.ulid as ulid_util
    import ulid
    ulid.parse(ulid_util.ulid())
    """
    ulid_bytes = int((timestamp or time.time()) * 1000).to_bytes(
        6, byteorder="big"
    ) + int(getrandbits(80)).to_bytes(10, byteorder="big")

    # This is base32 crockford encoding with the loop unrolled for performance
    #
    # This code is adapted from:
    # https://github.com/ahawker/ulid/blob/06289583e9de4286b4d80b4ad000d137816502ca/ulid/base32.py#L102
    #
    enc = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return (
        enc[(ulid_bytes[0] & 224) >> 5]
        + enc[ulid_bytes[0] & 31]
        + enc[(ulid_bytes[1] & 248) >> 3]
        + enc[((ulid_bytes[1] & 7) << 2) | ((ulid_bytes[2] & 192) >> 6)]
        + enc[((ulid_bytes[2] & 62) >> 1)]
        + enc[((ulid_bytes[2] & 1) << 4) | ((ulid_bytes[3] & 240) >> 4)]
        + enc[((ulid_bytes[3] & 15) << 1) | ((ulid_bytes[4] & 128) >> 7)]
        + enc[(ulid_bytes[4] & 124) >> 2]
        + enc[((ulid_bytes[4] & 3) << 3) | ((ulid_bytes[5] & 224) >> 5)]
        + enc[ulid_bytes[5] & 31]
        + enc[(ulid_bytes[6] & 248) >> 3]
        + enc[((ulid_bytes[6] & 7) << 2) | ((ulid_bytes[7] & 192) >> 6)]
        + enc[(ulid_bytes[7] & 62) >> 1]
        + enc[((ulid_bytes[7] & 1) << 4) | ((ulid_bytes[8] & 240) >> 4)]
        + enc[((ulid_bytes[8] & 15) << 1) | ((ulid_bytes[9] & 128) >> 7)]
        + enc[(ulid_bytes[9] & 124) >> 2]
        + enc[((ulid_bytes[9] & 3) << 3) | ((ulid_bytes[10] & 224) >> 5)]
        + enc[ulid_bytes[10] & 31]
        + enc[(ulid_bytes[11] & 248) >> 3]
        + enc[((ulid_bytes[11] & 7) << 2) | ((ulid_bytes[12] & 192) >> 6)]
        + enc[(ulid_bytes[12] & 62) >> 1]
        + enc[((ulid_bytes[12] & 1) << 4) | ((ulid_bytes[13] & 240) >> 4)]
        + enc[((ulid_bytes[13] & 15) << 1) | ((ulid_bytes[14] & 128) >> 7)]
        + enc[(ulid_bytes[14] & 124) >> 2]
        + enc[((ulid_bytes[14] & 3) << 3) | ((ulid_bytes[15] & 224) >> 5)]
        + enc[ulid_bytes[15] & 31]
    )
