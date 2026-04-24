"""Zeroconf constants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .discovery import ZeroconfDiscovery
    from .models import HaAsyncZeroconf

DOMAIN = "zeroconf"

ZEROCONF_TYPE = "_home-assistant._tcp.local."

REQUEST_TIMEOUT = 10000  # 10 seconds

DATA_INSTANCE: HassKey[HaAsyncZeroconf] = HassKey(DOMAIN)
DATA_DISCOVERY: HassKey[ZeroconfDiscovery] = HassKey(f"{DOMAIN}_discovery")
