"""Constants for the Hardware integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .models import HardwareData

DOMAIN = "hardware"

DATA_HARDWARE: HassKey[HardwareData] = HassKey(DOMAIN)
