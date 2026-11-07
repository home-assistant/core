"""Constants for the TrueNAS integration."""

from typing import Final

DOMAIN: Final = "truenas_ce"

# errname TrueNAS reports when the API key's user lacks the role for a call.
ERRNAME_PERMISSION_DENIED: Final = "EACCES"
