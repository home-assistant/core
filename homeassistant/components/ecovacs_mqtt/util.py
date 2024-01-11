"""Util module."""
from __future__ import annotations

import dataclasses
from enum import Enum
import random
import string
from typing import Any

from deebot_client.util import DisplayNameIntEnum

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


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert dataclass to dict and remove None fields."""
    dic = dataclasses.asdict(obj)
    for key, value in dic.copy().items():
        if value is None:
            dic.pop(key)
        elif isinstance(value, Enum):
            if isinstance(value, DisplayNameIntEnum):
                dic[key] = value.display_name
            else:
                dic[key] = value.value

    return dic
