"""Support for BloomSky weather station."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .hub import BloomSky

DOMAIN = "bloomsky"
DATA: HassKey[BloomSky] = HassKey(DOMAIN)
