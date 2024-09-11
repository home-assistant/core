"""Support for Automation Device Specification (ADS)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .hub import AdsHub

DOMAIN = "ads"

DATA_ADS: HassKey[AdsHub] = HassKey(DOMAIN)

CONF_ADS_VAR = "adsvar"

STATE_KEY_STATE = "state"
