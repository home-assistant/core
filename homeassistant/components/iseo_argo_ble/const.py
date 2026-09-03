"""Constants for the ISEO Argo BLE Lock integration."""

from homeassistant.const import Platform

DOMAIN = "iseo_argo_ble"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK]

# Config entry keys (CONF_ADDRESS and CONF_UUID come from homeassistant.const)
CONF_PRIV_SCALAR = "priv_scalar"
CONF_ADMIN_UUID = "admin_uuid"
CONF_ADMIN_PRIV_SCALAR = "admin_priv_scalar"

# Config flow field: opt in to enrolling the admin identity
CONF_ENABLE_ADMIN = "enable_admin"

# Action changing who may open the lock; administrators only
SERVICE_SET_CREDENTIAL_ENABLED = "set_credential_enabled"
ATTR_ENABLED = "enabled"

# Seconds to keep holding the BLE mutex after an admin session. The lock needs
# a moment to tear one down; talking to it again straight away makes the next
# operation fail.
ADMIN_SETTLE_DELAY = 2

# Default user subtype (gateway)
DEFAULT_USER_SUBTYPE: int = 17  # UserSubType.BT_GATEWAY
# The gateway subtype cannot read or modify the lock's user list, so user
# management runs as a second identity enrolled as a regular smartphone user.
ADMIN_USER_SUBTYPE: int = 16  # UserSubType.BT_SMARTPHONE
