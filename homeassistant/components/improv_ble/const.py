"""Constants for the Improv BLE integration."""

from __future__ import annotations

import asyncio

from homeassistant.util.hass_dict import HassKey

DOMAIN = "improv_ble"

PROVISIONING_FUTURES: HassKey[dict[str, asyncio.Future[str | None]]] = HassKey(DOMAIN)
