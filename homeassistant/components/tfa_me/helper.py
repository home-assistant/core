"""TFA.me station integration: helper.py."""

import re

_STATION_ID_RE = re.compile(r"^[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}$")


def resolve_tfa_host(address: str) -> str:
    """Resolve user input into a usable host for TFA.me."""

    # If the address contains an valid ID scheme "XXX-XXX-XXX", assume it's a station ID and
    # build the mDNS hostname. Otherwise, assume it's an IP or hostname.

    address = address.strip()
    # Station ID ?
    if _STATION_ID_RE.fullmatch(address):
        # Yes: "XXX-XXX-XXX" -> "tfa-me-xxx-xxx-xxx.local"
        return f"tfa-me-{address.lower()}.local"

    return address
