"""Constants for the LibreSync integration."""

from typing import Final

DOMAIN: Final = "libresync"

MANUFACTURER: Final = "Libre Wireless"
DEFAULT_NAME: Final = "LibreSync hub"

# Both ports are up in about 0.05 s on a LAN.
CONNECT_TIMEOUT: Final = 10.0

# Libre modules whose port 7777 the library cannot open: the Surround Hub wraps
# it in mutual TLS, the Stereo Hub HT resets a plaintext session. LSSDP names
# the module.
UNSUPPORTED_MODULES: Final = frozenset({"LS10"})
