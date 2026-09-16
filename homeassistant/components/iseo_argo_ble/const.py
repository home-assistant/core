"""Constants for the ISEO Argo BLE Lock integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "iseo_argo_ble"
PLATFORMS: list[Platform] = [Platform.LOCK]

# Config entry keys (CONF_ADDRESS and CONF_UUID come from homeassistant.const)
CONF_PRIV_SCALAR = "priv_scalar"

# Default user subtype (gateway)
DEFAULT_USER_SUBTYPE: int = 17  # UserSubType.BT_GATEWAY

# Name the lock stores for the Home Assistant gateway user.
GATEWAY_NAME = "Home Assistant"

# How often to poll the lock for door state.
STATE_POLL_INTERVAL = timedelta(seconds=30)

# Seconds the entity stays "unlocked" before the lock re-latches by itself.
RELOCK_DELAY = 5

# Seconds to wait after an unlock before re-polling the door state.
RELOCK_POLL_DELAY = 2
