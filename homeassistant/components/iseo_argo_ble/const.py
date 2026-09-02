"""Constants for the ISEO Argo BLE Lock integration."""

from homeassistant.const import Platform

DOMAIN = "iseo_argo_ble"
PLATFORMS: list[Platform] = [Platform.EVENT, Platform.LOCK]

# Config entry keys (CONF_ADDRESS and CONF_UUID come from homeassistant.const)
CONF_PRIV_SCALAR = "priv_scalar"

# Default user subtype (gateway)
DEFAULT_USER_SUBTYPE: int = 17  # UserSubType.BT_GATEWAY


def signal_access_log(entry_id: str) -> str:
    """Return the dispatcher signal carrying entries read from the access log."""
    return f"{DOMAIN}_{entry_id}_access_log"
