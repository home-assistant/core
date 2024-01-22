"""Ecovacs util functions."""

import random
import string


def get_client_device_id() -> str:
    """Get client device id."""
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )
