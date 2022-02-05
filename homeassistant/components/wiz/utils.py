"""WiZ utils."""
from __future__ import annotations

from pywizlight import BulbType

from .const import DEFAULT_NAME, SOCKET_DEVICE_STR


def _short_mac(mac: str) -> str:
    """Get the short mac address from the full mac."""
    return mac.replace(":", "").upper()[-6:]


def name_from_bulb_type_and_mac(bulb_type: BulbType, mac: str) -> str:
    """Generate a name from bulb_type and mac."""
    if SOCKET_DEVICE_STR in bulb_type.name:
        description = "Socket"
    else:
        description = bulb_type.bulb_type.value
    return f"{DEFAULT_NAME} {description} {_short_mac(mac)}"
