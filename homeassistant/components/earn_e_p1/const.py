"""Constants for the EARN-E P1 Meter integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

from .models import EarnEP1Data

DOMAIN = "earn_e_p1"
CONF_SERIAL = "serial"

# One UDP listener receives packets from every meter, so it is shared between
# config entries and reused by the config flow for discovery and validation.
EARN_E_P1_DATA: HassKey[EarnEP1Data] = HassKey(DOMAIN)
# Entries set up concurrently at startup, so creating and stopping the shared
# listener must not interleave or two of them race to bind the UDP port.
EARN_E_P1_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_lock")
