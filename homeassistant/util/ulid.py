"""Helpers to generate ulids."""

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


def ulid() -> str:
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
    enc = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ulid_upper_hex = f"{int(time.time()*1000):012X}{getrandbits(80):020X}".encode(
        "ascii"
    )

    # This is base32 crockford encoding with the loop unrolled for performance
    #
    # This code is adapted from:
    # https://github.com/ahawker/ulid/blob/06289583e9de4286b4d80b4ad000d137816502ca/ulid/base32.py#L102
    #

    return (
        enc[(ulid_upper_hex[0] & 224) >> 5]
        + enc[ulid_upper_hex[0] & 31]
        + enc[(ulid_upper_hex[1] & 248) >> 3]
        + enc[((ulid_upper_hex[1] & 7) << 2) | ((ulid_upper_hex[2] & 192) >> 6)]
        + enc[((ulid_upper_hex[2] & 62) >> 1)]
        + enc[((ulid_upper_hex[2] & 1) << 4) | ((ulid_upper_hex[3] & 240) >> 4)]
        + enc[((ulid_upper_hex[3] & 15) << 1) | ((ulid_upper_hex[4] & 128) >> 7)]
        + enc[(ulid_upper_hex[4] & 124) >> 2]
        + enc[((ulid_upper_hex[4] & 3) << 3) | ((ulid_upper_hex[5] & 224) >> 5)]
        + enc[ulid_upper_hex[5] & 31]
        + enc[(ulid_upper_hex[6] & 248) >> 3]
        + enc[((ulid_upper_hex[6] & 7) << 2) | ((ulid_upper_hex[7] & 192) >> 6)]
        + enc[(ulid_upper_hex[7] & 62) >> 1]
        + enc[((ulid_upper_hex[7] & 1) << 4) | ((ulid_upper_hex[8] & 240) >> 4)]
        + enc[((ulid_upper_hex[8] & 15) << 1) | ((ulid_upper_hex[9] & 128) >> 7)]
        + enc[(ulid_upper_hex[9] & 124) >> 2]
        + enc[((ulid_upper_hex[9] & 3) << 3) | ((ulid_upper_hex[10] & 224) >> 5)]
        + enc[ulid_upper_hex[10] & 31]
        + enc[(ulid_upper_hex[11] & 248) >> 3]
        + enc[((ulid_upper_hex[11] & 7) << 2) | ((ulid_upper_hex[12] & 192) >> 6)]
        + enc[(ulid_upper_hex[12] & 62) >> 1]
        + enc[((ulid_upper_hex[12] & 1) << 4) | ((ulid_upper_hex[13] & 240) >> 4)]
        + enc[((ulid_upper_hex[13] & 15) << 1) | ((ulid_upper_hex[14] & 128) >> 7)]
        + enc[(ulid_upper_hex[14] & 124) >> 2]
        + enc[((ulid_upper_hex[14] & 3) << 3) | ((ulid_upper_hex[15] & 224) >> 5)]
        + enc[ulid_upper_hex[15] & 31]
    )
