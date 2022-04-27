"""Helpers to generate ulids."""

from random import getrandbits
import time


# In the future once we require python 3.10 and above, we can
# create a new function that uses base64.b32encodehex to shorten
# these to 26 characters.
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
