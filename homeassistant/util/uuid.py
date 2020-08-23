"""Helpers to generate uuids."""

import random
import uuid


def uuid_v1mc_hex() -> str:
    """Generate a uuid1 with a random multicast MAC address.

    The uuid1 uses a random multicast MAC address instead of the real MAC address
    of the machine without the overhead of calling the getrandom() system call.

    This is effectively equivalent to PostgreSQL's uuid_generate_v1mc() function
    """
    return uuid.uuid1(node=random.getrandbits(48) | (1 << 40)).hex
