"""Constants for the LibreSync integration."""

from typing import Final

DOMAIN: Final = "libresync"

# Both identifiers are kept in the entry data whenever they are known. The
# unique_id is whichever was preferred when the entry was created.
CONF_SERIAL: Final = "serial"
CONF_UDN: Final = "udn"

MANUFACTURER: Final = "Libre Wireless"
DEFAULT_NAME: Final = "LibreSync hub"

# Both ports are up in about 0.05 s on a LAN.
CONNECT_TIMEOUT: Final = 10.0
