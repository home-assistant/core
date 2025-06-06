"""Support for Envisalink devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import EnvisalinkData

DOMAIN = "envisalink"

DATA_EVL: HassKey[EnvisalinkData] = HassKey(DOMAIN)
