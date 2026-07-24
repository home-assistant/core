"""Constants for the Improv BLE integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

DOMAIN = "improv_ble"

PROVISIONING_FUTURES: HassKey[dict[str, asyncio.Future[str]]] = HassKey(DOMAIN)

# Timeout in seconds to wait for another integration to register a next flow
# after successful provisioning (e.g., ESPHome discovering the device)
PROVISIONING_TIMEOUT = 10.0
