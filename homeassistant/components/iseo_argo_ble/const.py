"""Constants for the ISEO Argo BLE Lock integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "iseo_argo_ble"
PLATFORMS: list[Platform] = [Platform.LOCK]

# Config entry keys
CONF_ADDRESS = "address"
CONF_UUID = "uuid"
CONF_PRIV_SCALAR = "priv_scalar"

# Default user subtype (gateway)
DEFAULT_USER_SUBTYPE: int = 17  # UserSubType.BT_GATEWAY
