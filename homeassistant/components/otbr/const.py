"""Constants for the Open Thread Border Router integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .util import OTBRData

DOMAIN = "otbr"
DATA_OTBR: HassKey[OTBRData] = HassKey(DOMAIN)

DEFAULT_CHANNEL = 15
