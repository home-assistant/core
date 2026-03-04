"""Constants for the ISEO Argo BLE Lock integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "iseo_argo_ble"
PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR, Platform.SWITCH]

# Config entry keys
CONF_ADDRESS = "address"
CONF_UUID = "uuid"
CONF_PRIV_SCALAR = "priv_scalar"
CONF_USER_SUBTYPE = "user_subtype"
CONF_USER_MAP = "user_map"  # ConfigEntry.options key: {uuid_hex: ha_user_id}

# Optional admin identity — a second BT user enrolled with BT_SMARTPHONE subtype
# that can perform whitelist management without a physical Master Card tap.
# Both keys must be present together or not at all.
CONF_ADMIN_UUID = "admin_uuid"
CONF_ADMIN_PRIV_SCALAR = "admin_priv_scalar"

# Default user subtype (smartphone)
DEFAULT_USER_SUBTYPE: int = 16  # UserSubType.BT_SMARTPHONE

# Event fired into the HA bus for every new access-log entry.
EVENT_TYPE = "iseo_argo_ble_event"
