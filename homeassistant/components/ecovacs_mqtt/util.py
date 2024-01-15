"""Util module."""
from __future__ import annotations

import random
import string

from homeassistant.core import HomeAssistant

from .const import Mode


def get_client_device_id(hass: HomeAssistant, mode: Mode) -> str:
    """Return client device id."""
    if mode == Mode.SELF_HOSTED:
        return f"HA_{hass.config.location_name.strip().replace(' ', '_')}"

    # Generate a random device ID
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(12)
    )
